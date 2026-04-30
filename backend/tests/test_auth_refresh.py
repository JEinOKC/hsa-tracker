"""Tests for POST /auth/refresh endpoint.

Covers the token refresh flow that keeps users logged in when their
30-minute access token expires during normal app use.
"""

from datetime import datetime, timedelta

import jwt
from app.config import settings
from app.utils.security import create_access_token, create_refresh_token, decode_token


class TestRefreshToken:
    def test_returns_new_token_pair_for_valid_refresh_token(self, client, test_user):
        refresh = create_refresh_token({"sub": str(test_user.id)})
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_new_access_token_is_valid_and_for_correct_user(self, client, test_user):
        refresh = create_refresh_token({"sub": str(test_user.id)})
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})

        payload = decode_token(response.json()["access_token"])
        assert payload is not None
        assert payload["type"] == "access"
        assert payload["sub"] == str(test_user.id)

    def test_new_refresh_token_is_valid_and_has_correct_type(self, client, test_user):
        refresh = create_refresh_token({"sub": str(test_user.id)})
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})

        new_refresh = response.json()["refresh_token"]
        payload = decode_token(new_refresh)
        assert payload is not None
        assert payload["type"] == "refresh"
        assert payload["sub"] == str(test_user.id)

    def test_rejects_expired_refresh_token(self, client, test_user):
        # Create a token that expired in the past by passing a negative delta
        payload = {
            "sub": str(test_user.id),
            "type": "refresh",
            "exp": datetime.utcnow() - timedelta(seconds=1),
        }
        expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        response = client.post("/api/v1/auth/refresh", json={"refresh_token": expired_token})
        assert response.status_code == 401

    def test_rejects_access_token_used_as_refresh_token(self, client, test_user):
        access = create_access_token({"sub": str(test_user.id)})
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert response.status_code == 401

    def test_rejects_malformed_token(self, client):
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.valid.token"})
        assert response.status_code == 401

    def test_rejects_missing_refresh_token_field(self, client):
        response = client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 422

    def test_rejects_inactive_user(self, client, db_session, test_user):
        test_user.is_active = False
        db_session.commit()

        refresh = create_refresh_token({"sub": str(test_user.id)})
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert response.status_code == 401
