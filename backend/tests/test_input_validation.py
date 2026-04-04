"""Tests for input validation — length limits and character restrictions.

Enforcing these at the schema layer prevents data corruption and some
injection vectors before data reaches the database or downstream services.
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import PasskeyRegisterStartRequest


class TestUsernameValidation:

    def test_valid_username_accepted(self):
        r = PasskeyRegisterStartRequest(username="valid_user.123", display_name="Valid User")
        assert r.username == "valid_user.123"

    def test_username_too_short_rejected(self):
        with pytest.raises(ValidationError, match="at least 3 characters"):
            PasskeyRegisterStartRequest(username="ab", display_name="User")

    def test_username_too_long_rejected(self):
        with pytest.raises(ValidationError, match="50 characters or fewer"):
            PasskeyRegisterStartRequest(username="a" * 51, display_name="User")

    def test_username_with_spaces_rejected(self):
        with pytest.raises(ValidationError, match="letters, digits"):
            PasskeyRegisterStartRequest(username="user name", display_name="User")

    def test_username_with_html_tags_rejected(self):
        with pytest.raises(ValidationError, match="letters, digits"):
            PasskeyRegisterStartRequest(username="<script>", display_name="User")

    def test_username_with_sql_injection_rejected(self):
        with pytest.raises(ValidationError, match="letters, digits"):
            PasskeyRegisterStartRequest(username="user'; DROP TABLE users;--", display_name="User")

    def test_username_boundary_3_chars_accepted(self):
        r = PasskeyRegisterStartRequest(username="abc", display_name="User")
        assert r.username == "abc"

    def test_username_boundary_50_chars_accepted(self):
        r = PasskeyRegisterStartRequest(username="a" * 50, display_name="User")
        assert r.username == "a" * 50

    def test_username_with_allowed_special_chars(self):
        r = PasskeyRegisterStartRequest(username="user-name_v2.0", display_name="User")
        assert r.username == "user-name_v2.0"

    def test_username_is_stripped_of_whitespace(self):
        r = PasskeyRegisterStartRequest(username="  myuser  ", display_name="User")
        assert r.username == "myuser"


class TestDisplayNameValidation:

    def test_valid_display_name_accepted(self):
        r = PasskeyRegisterStartRequest(username="user123", display_name="Jane Doe")
        assert r.display_name == "Jane Doe"

    def test_display_name_too_long_rejected(self):
        with pytest.raises(ValidationError, match="100 characters or fewer"):
            PasskeyRegisterStartRequest(username="user123", display_name="A" * 101)

    def test_display_name_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            PasskeyRegisterStartRequest(username="user123", display_name="   ")

    def test_display_name_exactly_100_chars_accepted(self):
        r = PasskeyRegisterStartRequest(username="user123", display_name="A" * 100)
        assert len(r.display_name) == 100

    def test_display_name_is_stripped_of_whitespace(self):
        r = PasskeyRegisterStartRequest(username="user123", display_name="  Jane  ")
        assert r.display_name == "Jane"


class TestPasskeyRegisterStartEndpointValidation:
    """HTTP layer — validates that the API returns 422 for invalid inputs."""

    def test_short_username_returns_422(self, client):
        r = client.post("/api/v1/passkey/register/start", json={
            "username": "ab",
            "display_name": "User",
        })
        assert r.status_code == 422

    def test_username_with_special_chars_returns_422(self, client):
        r = client.post("/api/v1/passkey/register/start", json={
            "username": "<script>alert(1)</script>",
            "display_name": "User",
        })
        assert r.status_code == 422

    def test_empty_display_name_returns_422(self, client):
        r = client.post("/api/v1/passkey/register/start", json={
            "username": "validuser",
            "display_name": "",
        })
        assert r.status_code == 422

    def test_valid_input_passes_validation(self, client):
        r = client.post("/api/v1/passkey/register/start", json={
            "username": "validuser",
            "display_name": "Valid User",
        })
        # 200 OK (challenge generated) — not a 422 validation error
        assert r.status_code != 422
