"""Tests for password strength validation on registration and password-change endpoints.

Weak passwords on an app that stores PII, bank accounts, and health data
are an unacceptable risk, so we enforce complexity at the schema layer.
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest, ChangePasswordRequest


# ---------------------------------------------------------------------------
# Unit-level: Pydantic validator
# ---------------------------------------------------------------------------

class TestRegisterRequestPasswordStrength:

    def test_accepts_strong_password(self):
        r = RegisterRequest(
            email="user@example.com",
            password="Str0ng!Password#1",
            display_name="User",
        )
        assert r.password == "Str0ng!Password#1"

    def test_rejects_too_short(self):
        with pytest.raises(ValidationError, match="at least 12 characters"):
            RegisterRequest(email="u@e.com", password="Short!1A", display_name="U")

    def test_rejects_no_uppercase(self):
        with pytest.raises(ValidationError, match="uppercase"):
            RegisterRequest(email="u@e.com", password="nouppercase!1", display_name="U")

    def test_rejects_no_lowercase(self):
        with pytest.raises(ValidationError, match="lowercase"):
            RegisterRequest(email="u@e.com", password="NOLOWERCASE!1", display_name="U")

    def test_rejects_no_digit(self):
        with pytest.raises(ValidationError, match="digit"):
            RegisterRequest(email="u@e.com", password="NoDigitHere!!", display_name="U")

    def test_rejects_no_special_character(self):
        with pytest.raises(ValidationError, match="special character"):
            RegisterRequest(email="u@e.com", password="NoSpecialChar1A", display_name="U")

    def test_boundary_exactly_12_chars_accepted(self):
        r = RegisterRequest(email="u@e.com", password="Passw0rd!abc", display_name="U")
        assert r.password == "Passw0rd!abc"

    def test_boundary_11_chars_rejected(self):
        with pytest.raises(ValidationError, match="at least 12 characters"):
            RegisterRequest(email="u@e.com", password="Passw0rd!ab", display_name="U")


class TestChangePasswordRequestStrength:

    def test_accepts_strong_new_password(self):
        r = ChangePasswordRequest(
            current_password="anything",
            new_password="NewStr0ng!Pass#",
        )
        assert r.new_password == "NewStr0ng!Pass#"

    def test_rejects_weak_new_password(self):
        with pytest.raises(ValidationError, match="at least 12 characters"):
            ChangePasswordRequest(current_password="anything", new_password="weak")

    def test_current_password_not_validated_for_strength(self):
        """current_password is what the user already has — we don't re-validate it."""
        r = ChangePasswordRequest(
            current_password="weak",
            new_password="NewStr0ng!Pass#",
        )
        assert r.current_password == "weak"


# ---------------------------------------------------------------------------
# Integration-level: HTTP 422 returned by the API
# ---------------------------------------------------------------------------

class TestRegisterEndpointPasswordValidation:

    def test_register_with_weak_password_returns_422(self, client):
        r = client.post("/api/v1/auth/register", json={
            "email": "user@example.com",
            "password": "weakpass",
            "display_name": "User",
        })
        assert r.status_code == 422

    def test_register_with_strong_password_does_not_fail_validation(self, client):
        r = client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "Str0ng!Password#1",
            "display_name": "New User",
        })
        # 201 created or 400 duplicate — either way not a validation error
        assert r.status_code in (201, 400)
        assert r.status_code != 422
