"""Tests for rate limiting on authentication endpoints.

Each auth endpoint has a per-IP limit to mitigate brute-force and
enumeration attacks against this app that stores PII, bank, and health data.
"""

import pytest


class TestLoginRateLimit:
    """POST /auth/login is capped at 10 requests per minute."""

    def test_login_allows_requests_below_limit(self, client):
        # 3 attempts with wrong password should all get 401 (not 429)
        for _ in range(3):
            r = client.post("/api/v1/auth/login", json={"email": "no@example.com", "password": "wrong"})
            assert r.status_code != 429, f"Rate limit fired too early: {r.status_code}"

    def test_login_returns_429_after_exceeding_limit(self, client):
        # Exhaust the 10/minute limit
        for _ in range(10):
            client.post("/api/v1/auth/login", json={"email": "no@example.com", "password": "wrong"})
        r = client.post("/api/v1/auth/login", json={"email": "no@example.com", "password": "wrong"})
        assert r.status_code == 429


class TestRegisterRateLimit:
    """POST /auth/register is capped at 5 requests per minute."""

    def test_register_allows_requests_below_limit(self, client):
        for _ in range(3):
            r = client.post("/api/v1/auth/register", json={
                "email": "x@example.com",
                "password": "Str0ng!Password#1",
                "display_name": "X",
            })
            # 400 (duplicate email) or 201 — either way, not 429
            assert r.status_code != 429

    def test_register_returns_429_after_exceeding_limit(self, client):
        for i in range(5):
            client.post("/api/v1/auth/register", json={
                "email": f"u{i}@example.com",
                "password": "Str0ng!Password#1",
                "display_name": "User",
            })
        r = client.post("/api/v1/auth/register", json={
            "email": "overflow@example.com",
            "password": "Str0ng!Password#1",
            "display_name": "User",
        })
        assert r.status_code == 429


class TestPasskeyRegisterStartRateLimit:
    """POST /passkey/register/start is capped at 5 requests per minute."""

    def test_passkey_register_start_returns_429_after_exceeding_limit(self, client):
        for i in range(5):
            client.post("/api/v1/passkey/register/start", json={
                "username": f"user{i}",
                "display_name": "User",
            })
        r = client.post("/api/v1/passkey/register/start", json={
            "username": "overflow",
            "display_name": "Overflow",
        })
        assert r.status_code == 429


class TestPasskeyLoginStartRateLimit:
    """POST /passkey/login/start is capped at 10 requests per minute."""

    def test_passkey_login_start_returns_429_after_exceeding_limit(self, client):
        for _ in range(10):
            client.post("/api/v1/passkey/login/start", json={"username": "nobody"})
        r = client.post("/api/v1/passkey/login/start", json={"username": "nobody"})
        assert r.status_code == 429


class TestBackupCodeRateLimit:
    """POST /auth/backup-code/verify is capped at 5 requests per minute."""

    def test_backup_code_verify_returns_429_after_exceeding_limit(self, client):
        for _ in range(5):
            client.post(
                "/api/v1/auth/backup-code/verify",
                params={"email": "no@example.com", "password": "wrong", "backup_code": "XXXX-XXXX-XXXX"},
            )
        r = client.post(
            "/api/v1/auth/backup-code/verify",
            params={"email": "no@example.com", "password": "wrong", "backup_code": "XXXX-XXXX-XXXX"},
        )
        assert r.status_code == 429
