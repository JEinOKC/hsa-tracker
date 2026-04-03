"""Tests for family invite links and family PIN endpoints.

Covers:
  - POST /family-invites — create invite (returns URL + QR code)
  - GET /family-invites — list only caller's active invites
  - DELETE /family-invites/{token} — revoke own invite
  - GET /family-invites/validate/{token} — public validity check
  - register/start gating with family invite: expiry, PIN, burn on complete
  - GET /auth/family-pin — returns current PIN
  - POST /auth/family-pin/reset — generates new PIN
  - register/complete auto-generates family_pin for new user
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.models.user import FamilyInvite, User


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_invite(
    db_session,
    user_id,
    token="brave-silent-wolf",
    label=None,
    require_pin=True,
    hours_until_expiry=72,
    used=False,
):
    invite = FamilyInvite(
        id=uuid.uuid4(),
        token=token,
        label=label,
        created_by_user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(hours=hours_until_expiry),
        used_at=datetime.utcnow() if used else None,
        used_by_username="olduser" if used else None,
        require_pin=require_pin,
    )
    db_session.add(invite)
    db_session.commit()
    return invite


def _set_family_pin(db_session, user, pin="silent-falcon"):
    user.family_pin = pin
    db_session.commit()


# ── POST /family-invites ──────────────────────────────────────────────────────

class TestCreateInvite:
    def test_creates_invite_with_url_and_qr(self, client, auth_headers):
        response = client.post("/api/v1/family-invites", json={}, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert "token" in data
        assert data["invite_url"].endswith(f"/invite/{data['token']}")
        assert data["qr_code_data_url"].startswith("data:image/png;base64,")
        assert data["require_pin"] is True
        assert data["is_used"] is False

    def test_creates_invite_with_label_and_no_pin(self, client, auth_headers):
        response = client.post(
            "/api/v1/family-invites",
            json={"label": "for spouse", "require_pin": False},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["label"] == "for spouse"
        assert data["require_pin"] is False

    def test_requires_auth(self, client):
        response = client.post("/api/v1/family-invites", json={})
        assert response.status_code == 403


# ── GET /family-invites ───────────────────────────────────────────────────────

class TestListInvites:
    def test_returns_own_active_invites(self, client, auth_headers, db_session, test_user):
        _make_invite(db_session, test_user.id, token="alpha-one-two")
        _make_invite(db_session, test_user.id, token="beta-three-four")
        response = client.get("/api/v1/family-invites", headers=auth_headers)
        assert response.status_code == 200
        tokens = {i["token"] for i in response.json()}
        assert "alpha-one-two" in tokens
        assert "beta-three-four" in tokens

    def test_excludes_expired_invites(self, client, auth_headers, db_session, test_user):
        _make_invite(db_session, test_user.id, token="fresh-token-ok", hours_until_expiry=24)
        _make_invite(db_session, test_user.id, token="stale-token-bad", hours_until_expiry=-1)
        response = client.get("/api/v1/family-invites", headers=auth_headers)
        tokens = {i["token"] for i in response.json()}
        assert "fresh-token-ok" in tokens
        assert "stale-token-bad" not in tokens

    def test_excludes_used_invites(self, client, auth_headers, db_session, test_user):
        _make_invite(db_session, test_user.id, token="used-invite-gone", used=True)
        response = client.get("/api/v1/family-invites", headers=auth_headers)
        tokens = {i["token"] for i in response.json()}
        assert "used-invite-gone" not in tokens

    def test_excludes_other_users_invites(self, client, auth_headers, db_session):
        other = User(
            id=uuid.uuid4(), username="otheruser", display_name="Other",
            is_active=True, is_superuser=False,
        )
        db_session.add(other)
        db_session.commit()
        _make_invite(db_session, other.id, token="not-mine-token")
        response = client.get("/api/v1/family-invites", headers=auth_headers)
        tokens = {i["token"] for i in response.json()}
        assert "not-mine-token" not in tokens


# ── DELETE /family-invites/{token} ────────────────────────────────────────────

class TestRevokeInvite:
    def test_deletes_own_invite(self, client, auth_headers, db_session, test_user):
        _make_invite(db_session, test_user.id, token="delete-me-token")
        response = client.delete("/api/v1/family-invites/delete-me-token", headers=auth_headers)
        assert response.status_code == 204
        assert db_session.query(FamilyInvite).filter_by(token="delete-me-token").first() is None

    def test_cannot_revoke_others_invite(self, client, auth_headers, db_session):
        other = User(
            id=uuid.uuid4(), username="ownr", display_name="Owner",
            is_active=True, is_superuser=False,
        )
        db_session.add(other)
        db_session.commit()
        _make_invite(db_session, other.id, token="not-yours-token")
        response = client.delete("/api/v1/family-invites/not-yours-token", headers=auth_headers)
        assert response.status_code == 403

    def test_cannot_revoke_used_invite(self, client, auth_headers, db_session, test_user):
        _make_invite(db_session, test_user.id, token="already-used-one", used=True)
        response = client.delete("/api/v1/family-invites/already-used-one", headers=auth_headers)
        assert response.status_code == 400

    def test_returns_404_for_nonexistent(self, client, auth_headers):
        response = client.delete("/api/v1/family-invites/ghost-token", headers=auth_headers)
        assert response.status_code == 404


# ── GET /family-invites/validate/{token} ─────────────────────────────────────

class TestValidateInvite:
    def test_valid_invite(self, client, db_session, test_user):
        _make_invite(db_session, test_user.id, token="valid-open-invite", require_pin=True)
        response = client.get("/api/v1/family-invites/validate/valid-open-invite")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["require_pin"] is True
        assert data["expires_at"] is not None

    def test_expired_invite_returns_invalid(self, client, db_session, test_user):
        _make_invite(db_session, test_user.id, token="expired-invite-here", hours_until_expiry=-1)
        response = client.get("/api/v1/family-invites/validate/expired-invite-here")
        assert response.json()["valid"] is False

    def test_used_invite_returns_invalid(self, client, db_session, test_user):
        _make_invite(db_session, test_user.id, token="used-invite-check", used=True)
        response = client.get("/api/v1/family-invites/validate/used-invite-check")
        assert response.json()["valid"] is False

    def test_unknown_token_returns_invalid(self, client):
        response = client.get("/api/v1/family-invites/validate/no-such-token")
        assert response.json()["valid"] is False


# ── register/start with FamilyInvite ─────────────────────────────────────────

class TestFamilyInviteRegistration:
    def _start(self, client, username="newuser", invite_token=None, family_pin=None):
        body = {"username": username, "display_name": "New User"}
        if invite_token:
            body["invite_token"] = invite_token
        if family_pin:
            body["family_pin"] = family_pin
        return client.post("/api/v1/passkey/register/start", json=body)

    def test_valid_invite_no_pin_required(self, client, db_session, test_user):
        _make_invite(db_session, test_user.id, token="open-no-pin", require_pin=False)
        response = self._start(client, invite_token="open-no-pin")
        assert response.status_code == 200

    def test_valid_invite_correct_pin(self, client, db_session, test_user):
        _set_family_pin(db_session, test_user, "silent-falcon")
        _make_invite(db_session, test_user.id, token="pin-required-ok", require_pin=True)
        response = self._start(client, invite_token="pin-required-ok", family_pin="silent-falcon")
        assert response.status_code == 200

    def test_wrong_pin_rejected(self, client, db_session, test_user):
        _set_family_pin(db_session, test_user, "correct-pin")
        _make_invite(db_session, test_user.id, token="wrong-pin-test", require_pin=True)
        response = self._start(client, invite_token="wrong-pin-test", family_pin="wrong-pin")
        assert response.status_code == 403
        assert "incorrect family pin" in response.json()["detail"].lower()

    def test_missing_pin_rejected(self, client, db_session, test_user):
        _set_family_pin(db_session, test_user, "need-this-pin")
        _make_invite(db_session, test_user.id, token="missing-pin-test", require_pin=True)
        response = self._start(client, invite_token="missing-pin-test", family_pin=None)
        assert response.status_code == 403
        assert "family pin is required" in response.json()["detail"].lower()

    def test_expired_invite_rejected(self, client, db_session, test_user):
        _make_invite(db_session, test_user.id, token="expired-reg-token", hours_until_expiry=-1)
        response = self._start(client, invite_token="expired-reg-token")
        assert response.status_code == 403
        assert "expired" in response.json()["detail"].lower()

    def test_token_burned_after_complete(self, client, db_session, test_user):
        _set_family_pin(db_session, test_user, "burn-pin")
        _make_invite(db_session, test_user.id, token="burn-family-token", require_pin=True)

        self._start(client, username="burnfamilyuser", invite_token="burn-family-token", family_pin="burn-pin")

        with patch("app.api.v1.endpoints.passkey.verify_registration_credential") as mock_verify:
            mock_verify.return_value = {
                "credential_id": "cred-family-burn",
                "public_key": "pk-family",
                "sign_count": 0,
                "aaguid": "00000000-0000-0000-0000-000000000000",
            }
            response = client.post(
                "/api/v1/passkey/register/complete",
                json={"username": "burnfamilyuser", "credential": {"id": "fake", "response": {}}},
            )

        assert response.status_code == 201
        db_session.expire_all()
        invite = db_session.query(FamilyInvite).filter_by(token="burn-family-token").first()
        assert invite.is_used
        assert invite.used_by_username == "burnfamilyuser"

    def test_new_user_gets_family_pin(self, client, db_session, test_user):
        _make_invite(db_session, test_user.id, token="auto-pin-token", require_pin=False)
        self._start(client, username="autopinuser", invite_token="auto-pin-token")

        with patch("app.api.v1.endpoints.passkey.verify_registration_credential") as mock_verify:
            mock_verify.return_value = {
                "credential_id": "cred-auto-pin",
                "public_key": "pk-auto",
                "sign_count": 0,
                "aaguid": "00000000-0000-0000-0000-000000000000",
            }
            client.post(
                "/api/v1/passkey/register/complete",
                json={"username": "autopinuser", "credential": {"id": "fake", "response": {}}},
            )

        db_session.expire_all()
        user = db_session.query(User).filter_by(username="autopinuser").first()
        assert user is not None
        assert user.family_pin is not None
        assert len(user.family_pin) > 0


# ── GET /auth/family-pin ──────────────────────────────────────────────────────

class TestFamilyPin:
    def test_returns_current_pin(self, client, auth_headers, db_session, test_user):
        _set_family_pin(db_session, test_user, "current-pin")
        response = client.get("/api/v1/auth/family-pin", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["pin"] == "current-pin"

    def test_reset_returns_new_pin(self, client, auth_headers, db_session, test_user):
        _set_family_pin(db_session, test_user, "old-pin")
        response = client.post("/api/v1/auth/family-pin/reset", headers=auth_headers)
        assert response.status_code == 200
        new_pin = response.json()["pin"]
        assert new_pin != "old-pin"
        assert "-" in new_pin  # coolname 2-word format

    def test_reset_persists_to_db(self, client, auth_headers, db_session, test_user):
        response = client.post("/api/v1/auth/family-pin/reset", headers=auth_headers)
        new_pin = response.json()["pin"]
        db_session.expire_all()
        user = db_session.query(User).filter_by(id=test_user.id).first()
        assert user.family_pin == new_pin

    def test_auto_generates_pin_for_legacy_user(self, client, auth_headers, db_session, test_user):
        test_user.family_pin = None
        db_session.commit()
        response = client.get("/api/v1/auth/family-pin", headers=auth_headers)
        assert response.status_code == 200
        pin = response.json()["pin"]
        assert pin is not None
        assert "-" in pin  # coolname 2-word format
