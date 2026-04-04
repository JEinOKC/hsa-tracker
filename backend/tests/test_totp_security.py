"""Tests for TOTP security — replay attack prevention and lockout integration.

A TOTP code is valid for a 30-second window. Accepting the same code twice in
that window would allow an attacker who intercepts a code to bypass 2FA.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pyotp

from app.models.user import User, UserTOTP, UserBackupCode
from app.utils.security import hash_password, generate_totp_secret, hash_backup_code


@pytest.fixture
def totp_user(db_session):
    """A user with verified TOTP enabled."""
    secret = generate_totp_secret()
    user = User(
        id=uuid.uuid4(),
        username="totp_security_user",
        display_name="TOTP Security User",
        email="totp_security@example.com",
        hashed_password=hash_password("Str0ng!Password#1"),
        is_active=True,
        is_superuser=False,
        failed_login_count=0,
        locked_until=None,
    )
    db_session.add(user)
    db_session.flush()

    totp_record = UserTOTP(
        user_id=user.id,
        secret=secret,
        is_verified=True,
        verified_at=datetime.utcnow(),
        last_used_code=None,
        last_used_at=None,
    )
    db_session.add(totp_record)
    db_session.commit()
    db_session.refresh(user)
    return user, secret


class TestTOTPReplayPrevention:

    def test_valid_totp_code_succeeds_first_use(self, client, totp_user):
        user, secret = totp_user
        code = pyotp.TOTP(secret).now()
        r = client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": code,
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_same_totp_code_rejected_on_second_use_within_window(self, client, totp_user):
        user, secret = totp_user
        code = pyotp.TOTP(secret).now()

        # First use succeeds
        r1 = client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": code,
        })
        assert r1.status_code == 200

        # Immediate second use of the same code must be rejected
        r2 = client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": code,
        })
        assert r2.status_code == 401
        assert "already been used" in r2.json()["detail"]

    def test_replay_increments_failure_counter(self, client, db_session, totp_user):
        user, secret = totp_user
        code = pyotp.TOTP(secret).now()

        # Use the code once (resets counter to 0)
        client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": code,
        })

        db_session.refresh(user)
        count_after_success = user.failed_login_count  # should be 0

        # Replay attempt should increment the counter
        client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": code,
        })
        db_session.refresh(user)
        assert user.failed_login_count > count_after_success

    def test_last_used_code_stored_after_success(self, client, db_session, totp_user):
        user, secret = totp_user
        code = pyotp.TOTP(secret).now()

        client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": code,
        })

        totp_record = db_session.query(UserTOTP).filter(UserTOTP.user_id == user.id).first()
        assert totp_record.last_used_code == code
        assert totp_record.last_used_at is not None

    def test_same_code_reused_after_window_expiry_is_allowed(self, client, db_session, totp_user):
        """If the last_used_at is >30 s ago, the same numeric code can be reused
        (it maps to a different time step in practice, but we should not block it)."""
        user, secret = totp_user
        code = pyotp.TOTP(secret).now()

        # Simulate the code having been used >30 s ago
        totp_record = db_session.query(UserTOTP).filter(UserTOTP.user_id == user.id).first()
        totp_record.last_used_code = code
        totp_record.last_used_at = datetime.utcnow() - timedelta(seconds=31)
        db_session.commit()

        r = client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": code,
        })
        # Should succeed (window has passed; the replay guard does not fire)
        assert r.status_code == 200

    def test_invalid_totp_code_increments_failure_counter(self, client, db_session, totp_user):
        user, _ = totp_user
        client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": "000000",
        })
        db_session.refresh(user)
        assert user.failed_login_count == 1

    def test_totp_login_blocked_when_account_locked(self, client, db_session, totp_user):
        user, secret = totp_user
        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db_session.commit()

        code = pyotp.TOTP(secret).now()
        r = client.post("/api/v1/auth/totp/login", params={
            "email": "totp_security@example.com",
            "password": "Str0ng!Password#1",
            "totp_code": code,
        })
        assert r.status_code == 403
        assert "locked" in r.json()["detail"].lower()
