"""Tests for account lockout after repeated failed login attempts.

After 5 consecutive failures the account is locked for 15 minutes.
This prevents brute-force attacks against an app storing health and financial data.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from app.models.user import User, UserTOTP, UserBackupCode
from app.utils.security import hash_password, hash_backup_code, generate_totp_secret


@pytest.fixture
def password_user(db_session):
    """A user with an email/password credential."""
    user = User(
        id=uuid.uuid4(),
        username="lockout_test_user",
        display_name="Lockout Test",
        email="lockout@example.com",
        hashed_password=hash_password("Str0ng!Password#1"),
        is_active=True,
        is_superuser=False,
        failed_login_count=0,
        locked_until=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestLoginLockout:

    def test_failed_login_increments_counter(self, client, db_session, password_user):
        client.post("/api/v1/auth/login", json={
            "email": "lockout@example.com",
            "password": "WrongPassword!1",
        })
        db_session.refresh(password_user)
        assert password_user.failed_login_count == 1

    def test_five_failures_lock_the_account(self, client, db_session, password_user):
        for _ in range(5):
            client.post("/api/v1/auth/login", json={
                "email": "lockout@example.com",
                "password": "WrongPassword!1",
            })
        db_session.refresh(password_user)
        assert password_user.locked_until is not None
        assert password_user.locked_until > datetime.utcnow()

    def test_locked_account_returns_403(self, client, db_session, password_user):
        # Lock the account manually
        password_user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        password_user.failed_login_count = 5
        db_session.commit()

        r = client.post("/api/v1/auth/login", json={
            "email": "lockout@example.com",
            "password": "Str0ng!Password#1",
        })
        assert r.status_code == 403
        assert "locked" in r.json()["detail"].lower()

    def test_expired_lockout_allows_login(self, client, db_session, password_user):
        # Lock expired in the past
        password_user.locked_until = datetime.utcnow() - timedelta(seconds=1)
        password_user.failed_login_count = 5
        db_session.commit()

        r = client.post("/api/v1/auth/login", json={
            "email": "lockout@example.com",
            "password": "Str0ng!Password#1",
        })
        assert r.status_code == 200

    def test_successful_login_resets_failure_counter(self, client, db_session, password_user):
        # 2 failures followed by a success
        for _ in range(2):
            client.post("/api/v1/auth/login", json={
                "email": "lockout@example.com",
                "password": "WrongPassword!1",
            })
        client.post("/api/v1/auth/login", json={
            "email": "lockout@example.com",
            "password": "Str0ng!Password#1",
        })
        db_session.refresh(password_user)
        assert password_user.failed_login_count == 0
        assert password_user.locked_until is None


class TestBackupCodeLockout:

    @pytest.fixture
    def user_with_backup_code(self, db_session, password_user):
        code = "AAAA-BBBB-CCCC"
        bc = UserBackupCode(
            user_id=password_user.id,
            code_hash=hash_backup_code(code),
        )
        db_session.add(bc)
        db_session.commit()
        return password_user, code

    def test_invalid_backup_code_increments_counter(self, client, db_session, user_with_backup_code):
        user, _ = user_with_backup_code
        client.post("/api/v1/auth/backup-code/verify", params={
            "email": "lockout@example.com",
            "password": "Str0ng!Password#1",
            "backup_code": "XXXX-XXXX-XXXX",
        })
        db_session.refresh(user)
        assert user.failed_login_count == 1

    def test_locked_account_rejects_backup_code(self, client, db_session, user_with_backup_code):
        user, valid_code = user_with_backup_code
        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db_session.commit()

        r = client.post("/api/v1/auth/backup-code/verify", params={
            "email": "lockout@example.com",
            "password": "Str0ng!Password#1",
            "backup_code": valid_code,
        })
        assert r.status_code == 403

    def test_valid_backup_code_resets_counter(self, client, db_session, user_with_backup_code):
        user, valid_code = user_with_backup_code
        user.failed_login_count = 3
        db_session.commit()

        client.post("/api/v1/auth/backup-code/verify", params={
            "email": "lockout@example.com",
            "password": "Str0ng!Password#1",
            "backup_code": valid_code,
        })
        db_session.refresh(user)
        assert user.failed_login_count == 0
