"""Integration tests for passkey authentication endpoints.

WebAuthn credential verification is mocked because it requires real
authenticator hardware. Everything else (HTTP flow, DB operations,
challenge management, error handling) is tested for real.
"""

import uuid
from unittest.mock import patch

from app.models.user import User, UserPasskey
from app.utils.security import decode_token


class TestPasskeyRegisterStart:
    def test_returns_options_for_new_user(self, client):
        response = client.post(
            "/api/v1/passkey/register/start",
            json={"username": "newuser", "display_name": "New User"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "options" in data
        assert data["username"] == "newuser"
        assert "challenge" in data["options"]

    def test_rejects_existing_username(self, client, test_user):
        response = client.post(
            "/api/v1/passkey/register/start",
            json={"username": "testuser", "display_name": "Another User"},
        )
        assert response.status_code == 400
        assert "already taken" in response.json()["detail"].lower()

    def test_missing_username_returns_422(self, client):
        response = client.post(
            "/api/v1/passkey/register/start",
            json={"display_name": "No Username"},
        )
        assert response.status_code == 422

    def test_missing_display_name_returns_422(self, client):
        response = client.post(
            "/api/v1/passkey/register/start",
            json={"username": "namer"},
        )
        assert response.status_code == 422


class TestPasskeyRegisterComplete:
    @patch("app.api.v1.endpoints.passkey.verify_registration_credential")
    def test_creates_user_and_passkey(self, mock_verify, client, db_session):
        # Start registration
        start = client.post(
            "/api/v1/passkey/register/start",
            json={"username": "newuser", "display_name": "New User"},
        )
        assert start.status_code == 200

        mock_verify.return_value = {
            "credential_id": "fake-credential-id",
            "public_key": "fake-public-key",
            "sign_count": 0,
            "aaguid": "00000000-0000-0000-0000-000000000000",
        }

        # Complete registration
        response = client.post(
            "/api/v1/passkey/register/complete",
            json={
                "username": "newuser",
                "credential": {"id": "fake", "response": {}},
                "device_name": "Test Device",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["display_name"] == "New User"

        # Verify user was persisted
        user = db_session.query(User).filter(User.username == "newuser").first()
        assert user is not None
        assert user.hashed_password is None  # passkey-only, no password

        # Verify passkey was persisted
        passkey = (
            db_session.query(UserPasskey)
            .filter(UserPasskey.user_id == user.id)
            .first()
        )
        assert passkey is not None
        assert passkey.credential_id == "fake-credential-id"
        assert passkey.device_name == "Test Device"

    def test_rejects_without_prior_start(self, client):
        response = client.post(
            "/api/v1/passkey/register/complete",
            json={
                "username": "neverstarted",
                "credential": {"id": "fake"},
            },
        )
        assert response.status_code == 400

    @patch("app.api.v1.endpoints.passkey.verify_registration_credential")
    def test_rejects_failed_verification(self, mock_verify, client):
        client.post(
            "/api/v1/passkey/register/start",
            json={"username": "failuser", "display_name": "Fail User"},
        )

        mock_verify.side_effect = Exception("Invalid attestation")

        response = client.post(
            "/api/v1/passkey/register/complete",
            json={
                "username": "failuser",
                "credential": {"id": "bad"},
            },
        )
        assert response.status_code == 400
        assert "verification failed" in response.json()["detail"].lower()


class TestPasskeyLoginStart:
    def test_returns_options_for_user_with_passkey(
        self, client, test_user_with_passkey
    ):
        response = client.post(
            "/api/v1/passkey/login/start",
            json={"username": "passkeyuser"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "options" in data
        assert "challenge" in data["options"]
        assert data["username"] == "passkeyuser"

    def test_rejects_unknown_user(self, client):
        response = client.post(
            "/api/v1/passkey/login/start",
            json={"username": "nonexistent"},
        )
        assert response.status_code == 404

    def test_rejects_inactive_user(self, client, db_session):
        user = User(
            id=uuid.uuid4(),
            username="disabled",
            display_name="Disabled",
            is_active=False,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.commit()
        response = client.post(
            "/api/v1/passkey/login/start",
            json={"username": "disabled"},
        )
        assert response.status_code == 403

    def test_rejects_user_without_passkeys(self, client, test_user):
        """test_user has no passkey credentials registered."""
        response = client.post(
            "/api/v1/passkey/login/start",
            json={"username": "testuser"},
        )
        assert response.status_code == 400
        assert "no passkeys" in response.json()["detail"].lower()


class TestPasskeyLoginComplete:
    def test_returns_valid_tokens(self, client, db_session, test_user_with_passkey):
        # Start login (stores challenge - must happen before mock)
        start_resp = client.post(
            "/api/v1/passkey/login/start",
            json={"username": "passkeyuser"},
        )
        assert start_resp.status_code == 200

        # Mock verification for the complete step
        with patch(
            "app.api.v1.endpoints.passkey.verify_authentication_credential"
        ) as mock_verify:
            mock_verify.return_value = {
                "verified": True,
                "new_sign_count": 1,
                "credential_id": "test-credential-id-base64url",
            }

            response = client.post(
                "/api/v1/passkey/login/complete",
                json={
                    "username": "passkeyuser",
                    "credential": {
                        "id": "test-credential-id-base64url",
                        "rawId": "test-credential-id-base64url",
                        "response": {},
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify the access token is valid and contains the user ID
        payload = decode_token(data["access_token"])
        assert payload is not None
        assert payload["sub"] == str(test_user_with_passkey.id)
        assert payload["type"] == "access"

    def test_updates_sign_count(self, client, db_session, test_user_with_passkey):
        client.post(
            "/api/v1/passkey/login/start",
            json={"username": "passkeyuser"},
        )

        with patch(
            "app.api.v1.endpoints.passkey.verify_authentication_credential"
        ) as mock_verify:
            mock_verify.return_value = {
                "verified": True,
                "new_sign_count": 5,
                "credential_id": "test-credential-id-base64url",
            }

            client.post(
                "/api/v1/passkey/login/complete",
                json={
                    "username": "passkeyuser",
                    "credential": {
                        "id": "test-credential-id-base64url",
                        "rawId": "test-credential-id-base64url",
                        "response": {},
                    },
                },
            )

        # Verify sign count was updated in DB
        passkey = (
            db_session.query(UserPasskey)
            .filter(UserPasskey.credential_id == "test-credential-id-base64url")
            .first()
        )
        assert passkey.sign_count == 5
        assert passkey.last_used_at is not None

    def test_rejects_without_prior_start(self, client):
        response = client.post(
            "/api/v1/passkey/login/complete",
            json={
                "username": "nostart",
                "credential": {"id": "fake"},
            },
        )
        assert response.status_code == 400

    def test_rejects_failed_verification(self, client, test_user_with_passkey):
        client.post(
            "/api/v1/passkey/login/start",
            json={"username": "passkeyuser"},
        )

        with patch(
            "app.api.v1.endpoints.passkey.verify_authentication_credential"
        ) as mock_verify:
            mock_verify.side_effect = Exception("Signature mismatch")

            response = client.post(
                "/api/v1/passkey/login/complete",
                json={
                    "username": "passkeyuser",
                    "credential": {
                        "id": "test-credential-id-base64url",
                        "rawId": "test-credential-id-base64url",
                        "response": {},
                    },
                },
            )

        assert response.status_code == 401
        assert "verification failed" in response.json()["detail"].lower()
