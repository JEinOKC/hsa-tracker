"""Tests for the send_push_to_user helper."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.utils.push import send_push_to_user


@pytest.fixture
def user_id(db_session):
    user = User(
        id=uuid.uuid4(),
        username=f"pushtest_{uuid.uuid4().hex[:8]}",
        display_name="Push Test User",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    return user.id


@pytest.fixture
def active_sub(db_session, user_id):
    sub = PushSubscription(
        id=uuid.uuid4(),
        user_id=user_id,
        endpoint="https://push.example.com/sub/1",
        p256dh="fake-p256dh",
        auth="fake-auth",
        is_active=True,
    )
    db_session.add(sub)
    db_session.commit()
    return sub


@pytest.fixture
def inactive_sub(db_session, user_id):
    sub = PushSubscription(
        id=uuid.uuid4(),
        user_id=user_id,
        endpoint="https://push.example.com/sub/2",
        p256dh="fake-p256dh",
        auth="fake-auth",
        is_active=False,
    )
    db_session.add(sub)
    db_session.commit()
    return sub


def test_returns_zero_when_vapid_not_configured(db_session, user_id):
    with patch("app.utils.push.settings") as mock_settings:
        mock_settings.vapid_private_key = None
        result = send_push_to_user(user_id, "Title", "Body", db_session)
    assert result == 0


def test_sends_to_active_subscriptions(db_session, user_id, active_sub):
    with patch("app.utils.push.settings") as mock_settings:
        mock_settings.vapid_private_key = "fake-private-key"
        mock_settings.vapid_claims_email = "mailto:test@example.com"
        # Patch pywebpush.webpush at source — send_push_to_user imports it lazily
        with patch("pywebpush.webpush") as mock_webpush:
            result = send_push_to_user(user_id, "Title", "Body", db_session)

    assert result == 1
    mock_webpush.assert_called_once()


def test_skips_inactive_subscriptions(db_session, user_id, inactive_sub):
    with patch("app.utils.push.settings") as mock_settings:
        mock_settings.vapid_private_key = "fake-private-key"
        mock_settings.vapid_claims_email = "mailto:test@example.com"
        with patch("pywebpush.webpush") as mock_webpush:
            result = send_push_to_user(user_id, "Title", "Body", db_session)

    assert result == 0
    mock_webpush.assert_not_called()


def test_url_included_in_payload_when_provided(db_session, user_id, active_sub):
    import json

    with patch("app.utils.push.settings") as mock_settings:
        mock_settings.vapid_private_key = "fake-private-key"
        mock_settings.vapid_claims_email = "mailto:test@example.com"
        with patch("pywebpush.webpush") as mock_webpush:
            send_push_to_user(user_id, "Title", "Body", db_session, url="/review")

    call_kwargs = mock_webpush.call_args.kwargs
    payload = json.loads(call_kwargs["data"])
    assert payload["url"] == "/review"


def test_url_defaults_to_slash(db_session, user_id, active_sub):
    import json

    with patch("app.utils.push.settings") as mock_settings:
        mock_settings.vapid_private_key = "fake-private-key"
        mock_settings.vapid_claims_email = "mailto:test@example.com"
        with patch("pywebpush.webpush") as mock_webpush:
            send_push_to_user(user_id, "Title", "Body", db_session)

    call_kwargs = mock_webpush.call_args.kwargs
    payload = json.loads(call_kwargs["data"])
    assert payload["url"] == "/"


def test_deactivates_subscription_on_410(db_session, user_id, active_sub):
    from pywebpush import WebPushException

    gone_response = MagicMock()
    gone_response.status_code = 410

    with patch("app.utils.push.settings") as mock_settings:
        mock_settings.vapid_private_key = "fake-private-key"
        mock_settings.vapid_claims_email = "mailto:test@example.com"
        with patch("pywebpush.webpush", side_effect=WebPushException("Gone", response=gone_response)):
            result = send_push_to_user(user_id, "Title", "Body", db_session)

    assert result == 0
    db_session.refresh(active_sub)
    assert active_sub.is_active is False
