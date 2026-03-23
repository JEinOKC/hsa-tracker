"""Tests for auth dependencies - JWT token validation and user extraction."""

import uuid

from app.models.user import User
from app.utils.security import create_access_token, create_refresh_token


class TestGetCurrentUser:
    def test_valid_token_returns_user(self, client, test_user, auth_headers):
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["display_name"] == "Test User"

    def test_missing_token_returns_403(self, client):
        """HTTPBearer with auto_error=True returns 403 when no token provided."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403

    def test_invalid_token_returns_401(self, client):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert response.status_code == 401

    def test_refresh_token_rejected_for_access(self, client, test_user):
        """Refresh tokens must not work on endpoints expecting access tokens."""
        refresh = create_refresh_token({"sub": str(test_user.id)})
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert response.status_code == 401

    def test_inactive_user_returns_403(self, client, db_session):
        user = User(
            id=uuid.uuid4(),
            username="inactive",
            display_name="Inactive User",
            is_active=False,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.commit()
        token = create_access_token({"sub": str(user.id)})
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_token_for_nonexistent_user_returns_401(self, client):
        token = create_access_token({"sub": str(uuid.uuid4())})
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
