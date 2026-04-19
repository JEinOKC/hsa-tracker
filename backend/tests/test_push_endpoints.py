"""Tests for push notification endpoints."""

import uuid
from unittest.mock import patch

import pytest

from app.models.push_subscription import PushSubscription


SAMPLE_ENDPOINT = "https://push.example.com/sub/abc123"
SAMPLE_KEYS = {"p256dh": "fake-p256dh-key", "auth": "fake-auth-key"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def subscription(db_session, test_user):
    sub = PushSubscription(
        id=uuid.uuid4(),
        user_id=test_user.id,
        endpoint=SAMPLE_ENDPOINT,
        p256dh=SAMPLE_KEYS["p256dh"],
        auth=SAMPLE_KEYS["auth"],
        is_active=True,
    )
    db_session.add(sub)
    db_session.commit()
    return sub


# ---------------------------------------------------------------------------
# GET /push/vapid-public-key
# ---------------------------------------------------------------------------

def test_vapid_public_key_returns_key(client):
    with patch("app.api.v1.endpoints.push.settings") as mock_settings:
        mock_settings.vapid_public_key = "fake-vapid-public-key"
        response = client.get("/api/v1/push/vapid-public-key")
    assert response.status_code == 200
    assert response.json()["vapid_public_key"] == "fake-vapid-public-key"


def test_vapid_public_key_returns_empty_when_not_configured(client):
    with patch("app.api.v1.endpoints.push.settings") as mock_settings:
        mock_settings.vapid_public_key = None
        response = client.get("/api/v1/push/vapid-public-key")
    assert response.status_code == 200
    assert response.json()["vapid_public_key"] == ""


# ---------------------------------------------------------------------------
# POST /push/subscribe
# ---------------------------------------------------------------------------

def test_subscribe_creates_new_subscription(client, auth_headers, db_session, test_user):
    response = client.post(
        "/api/v1/push/subscribe",
        json={"endpoint": SAMPLE_ENDPOINT, "keys": SAMPLE_KEYS},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["ok"] is True

    sub = db_session.query(PushSubscription).filter(
        PushSubscription.endpoint == SAMPLE_ENDPOINT
    ).first()
    assert sub is not None
    assert sub.user_id == test_user.id
    assert sub.p256dh == SAMPLE_KEYS["p256dh"]
    assert sub.is_active is True


def test_subscribe_reactivates_existing_subscription(client, auth_headers, db_session, subscription):
    subscription.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/push/subscribe",
        json={"endpoint": SAMPLE_ENDPOINT, "keys": SAMPLE_KEYS},
        headers=auth_headers,
    )
    assert response.status_code == 201
    db_session.refresh(subscription)
    assert subscription.is_active is True


def test_subscribe_requires_auth(client):
    response = client.post(
        "/api/v1/push/subscribe",
        json={"endpoint": SAMPLE_ENDPOINT, "keys": SAMPLE_KEYS},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /push/subscribe
# ---------------------------------------------------------------------------

def test_unsubscribe_removes_subscription(client, auth_headers, db_session, subscription):
    response = client.request(
        "DELETE",
        "/api/v1/push/subscribe",
        json={"endpoint": SAMPLE_ENDPOINT, "keys": SAMPLE_KEYS},
        headers=auth_headers,
    )
    assert response.status_code == 204

    remaining = db_session.query(PushSubscription).filter(
        PushSubscription.endpoint == SAMPLE_ENDPOINT
    ).first()
    assert remaining is None


def test_unsubscribe_requires_auth(client):
    response = client.request(
        "DELETE",
        "/api/v1/push/subscribe",
        json={"endpoint": SAMPLE_ENDPOINT, "keys": SAMPLE_KEYS},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /push/test
# ---------------------------------------------------------------------------

def test_send_test_push_calls_helper(client, auth_headers, test_user):
    with patch("app.api.v1.endpoints.push.send_push_to_user", return_value=1) as mock_send:
        response = client.post("/api/v1/push/test", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["sent_to"] == 1
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["user_id"] == test_user.id
    assert call_kwargs["title"] == "HSA Tracker"
    assert call_kwargs["body"] == "Test notification — push is working!"


def test_send_test_push_returns_zero_when_no_vapid(client, auth_headers):
    with patch("app.utils.push.settings") as mock_settings:
        mock_settings.vapid_private_key = None
        response = client.post("/api/v1/push/test", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["sent_to"] == 0


def test_send_test_push_requires_auth(client):
    response = client.post("/api/v1/push/test")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /push/notify-hsa-review
# ---------------------------------------------------------------------------

def test_notify_hsa_review_sends_singular_body(client, auth_headers, test_user):
    with patch("app.api.v1.endpoints.push.send_push_to_user", return_value=1) as mock_send:
        response = client.post(
            "/api/v1/push/notify-hsa-review",
            json={"count": 1},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["sent_to"] == 1
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["body"] == "1 new transaction may be HSA-eligible"
    assert call_kwargs["url"] == "/review"


def test_notify_hsa_review_sends_plural_body(client, auth_headers, test_user):
    with patch("app.api.v1.endpoints.push.send_push_to_user", return_value=1) as mock_send:
        response = client.post(
            "/api/v1/push/notify-hsa-review",
            json={"count": 5},
            headers=auth_headers,
        )

    assert response.status_code == 200
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["body"] == "5 new transactions may be HSA-eligible"


def test_notify_hsa_review_skips_push_for_zero_count(client, auth_headers):
    with patch("app.api.v1.endpoints.push.send_push_to_user") as mock_send:
        response = client.post(
            "/api/v1/push/notify-hsa-review",
            json={"count": 0},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["sent_to"] == 0
    mock_send.assert_not_called()


def test_notify_hsa_review_requires_auth(client):
    response = client.post("/api/v1/push/notify-hsa-review", json={"count": 1})
    assert response.status_code == 403
