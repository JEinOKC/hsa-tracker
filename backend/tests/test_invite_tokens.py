"""Tests for invite-token-gated registration and the /config endpoint.

Covers:
  - GET /config returns require_invite flag
  - Registration blocked without token when REQUIRE_INVITE=true
  - Registration blocked with invalid / already-used token
  - Registration succeeds with valid token; token is burned
  - Token burn is idempotent (re-use attempt rejected)
  - Open registration (REQUIRE_INVITE=false) ignores any token field
"""

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest

from app.models.user import RegistrationToken, User


# ── /config endpoint ──────────────────────────────────────────────────────────

class TestAppConfig:
    def test_returns_false_by_default(self, client):
        response = client.get("/api/v1/config")
        assert response.status_code == 200
        assert response.json() == {"require_invite": False}

    def test_returns_true_when_enabled(self, client):
        with patch("app.api.v1.endpoints.app_config.settings") as mock_settings:
            mock_settings.require_invite = True
            response = client.get("/api/v1/config")
        assert response.status_code == 200
        assert response.json() == {"require_invite": True}


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_token(db_session, token_str="brave-silent-wolf", label=None, used=False):
    token = RegistrationToken(
        id=uuid.uuid4(),
        token=token_str,
        label=label,
        used_at=datetime.utcnow() if used else None,
        used_by_username="olduser" if used else None,
    )
    db_session.add(token)
    db_session.commit()
    return token


# ── registration gating ───────────────────────────────────────────────────────

class TestInviteGatedRegistration:
    """When REQUIRE_INVITE=true the register/start endpoint enforces tokens."""

    def _start(self, client, username="newuser", invite_token=None):
        body = {"username": username, "display_name": "New User"}
        if invite_token is not None:
            body["invite_token"] = invite_token
        return client.post("/api/v1/passkey/register/start", json=body)

    def test_blocked_without_token(self, client, db_session):
        with patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            response = self._start(client, invite_token=None)
        assert response.status_code == 403
        assert "required" in response.json()["detail"].lower()

    def test_blocked_with_invalid_token(self, client, db_session):
        with patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            response = self._start(client, invite_token="not-a-real-token")
        assert response.status_code == 403
        assert "invalid" in response.json()["detail"].lower()

    def test_blocked_with_already_used_token(self, client, db_session):
        _make_token(db_session, token_str="spent-token-here", used=True)
        with patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            response = self._start(client, invite_token="spent-token-here")
        assert response.status_code == 403
        assert "already been used" in response.json()["detail"].lower()

    def test_valid_token_allows_registration_start(self, client, db_session):
        _make_token(db_session, token_str="valid-fresh-token")
        with patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            response = self._start(client, invite_token="valid-fresh-token")
        assert response.status_code == 200
        assert "options" in response.json()

    def test_token_burned_after_complete(self, client, db_session):
        _make_token(db_session, token_str="burn-me-token")

        with patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            self._start(client, username="burnuser", invite_token="burn-me-token")

        with patch("app.api.v1.endpoints.passkey.verify_registration_credential") as mock_verify, \
             patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            mock_verify.return_value = {
                "credential_id": "fake-cred-burn",
                "public_key": "fake-pk",
                "sign_count": 0,
                "aaguid": "00000000-0000-0000-0000-000000000000",
            }
            response = client.post(
                "/api/v1/passkey/register/complete",
                json={
                    "username": "burnuser",
                    "credential": {"id": "fake", "response": {}},
                },
            )

        assert response.status_code == 201

        # Token must now be marked used
        db_session.expire_all()
        token = db_session.query(RegistrationToken).filter_by(token="burn-me-token").first()
        assert token.is_used
        assert token.used_by_username == "burnuser"

    def test_burned_token_cannot_be_reused(self, client, db_session):
        """After a successful registration, the same token is rejected for a second attempt."""
        _make_token(db_session, token_str="reuse-attempt-token")

        with patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            self._start(client, username="firstuser", invite_token="reuse-attempt-token")

        with patch("app.api.v1.endpoints.passkey.verify_registration_credential") as mock_verify, \
             patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            mock_verify.return_value = {
                "credential_id": "cred-first",
                "public_key": "pk-first",
                "sign_count": 0,
                "aaguid": "00000000-0000-0000-0000-000000000000",
            }
            client.post(
                "/api/v1/passkey/register/complete",
                json={"username": "firstuser", "credential": {"id": "fake", "response": {}}},
            )

        # Now try to use the same token for a second registration
        with patch("app.api.v1.endpoints.passkey.settings") as mock_settings:
            mock_settings.require_invite = True
            mock_settings.webauthn_rp_id = "localhost"
            mock_settings.webauthn_origin = "http://localhost:3001"
            response = self._start(client, username="seconduser", invite_token="reuse-attempt-token")

        assert response.status_code == 403
        assert "already been used" in response.json()["detail"].lower()


# ── open registration ─────────────────────────────────────────────────────────

class TestOpenRegistration:
    """When REQUIRE_INVITE=false (default) tokens are ignored."""

    def test_no_token_needed(self, client):
        response = client.post(
            "/api/v1/passkey/register/start",
            json={"username": "openuser", "display_name": "Open User"},
        )
        assert response.status_code == 200

    def test_supplying_token_is_harmless(self, client):
        response = client.post(
            "/api/v1/passkey/register/start",
            json={
                "username": "openuser2",
                "display_name": "Open User 2",
                "invite_token": "anything-goes",
            },
        )
        assert response.status_code == 200
