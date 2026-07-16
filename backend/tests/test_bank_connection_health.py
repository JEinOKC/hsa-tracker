"""Tests for bank connection health tracking, error handling, and seamless re-connect.

Covers:
- Sync marks connection as 'disconnected' on SimpleFIN auth errors
- Sync marks connection as 'error' on other SimpleFIN errors
- Successful sync resets connection_status to 'connected'
- Re-connect exact match reuses existing row (preserves transaction history)
- sync-all returns per-account outcomes
- sync-all skips already-disconnected accounts
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.models.bank import BankConnection
from app.providers.base import ExternalAccount, ExternalTransaction
from app.providers.simplefin.client import (
    SimpleFINAuthError,
    SimpleFINError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connection(
    db_session,
    user_id=None,
    provider_account_id="https://bridge.simplefin.org/simplefin/accounts/acct001",
    token="https://u:p@beta-bridge.simplefin.org/simplefin",
    account_type="depository",
    account_subtype="hsa",
    account_name="HSA Checking",
    institution_name="First National Bank",
    last_four=None,
    connection_status="connected",
):
    conn = BankConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="simplefin",
        provider_account_id=provider_account_id,
        account_name=account_name,
        account_type=account_type,
        account_subtype=account_subtype,
        institution_name=institution_name,
        last_four=last_four,
        currency="USD",
        enrollment_token=token,
        is_active=True,
        connection_status=connection_status,
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)
    return conn


def _make_external_account(
    account_id="https://bridge.simplefin.org/simplefin/accounts/acct001",
    name="HSA Checking",
    subtype="hsa",
    institution_name="First National Bank",
    last_four=None,
):
    return ExternalAccount(
        id=account_id,
        name=name,
        type="depository",
        subtype=subtype,
        currency="USD",
        institution_name=institution_name,
        provider="simplefin",
        last_four=last_four,
    )


def _make_external_txn(txn_id="txn_health_001", amount="-50.00"):
    return ExternalTransaction(
        id=txn_id,
        account_id="https://bridge.simplefin.org/simplefin/accounts/acct001",
        date=date(2026, 3, 1),
        description="CVS Pharmacy",
        amount=Decimal(amount),
        type="",
        status="posted",
        provider="simplefin",
        details={},
    )


# ---------------------------------------------------------------------------
# Sync error handling
# ---------------------------------------------------------------------------

class TestSyncConnectionErrors:
    def test_sync_auth_error_marks_disconnected_and_returns_409(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.side_effect = SimpleFINAuthError(
            "SimpleFIN access URL credentials are invalid or expired."
        )

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 409
        assert "invalid or expired" in resp.json()["detail"].lower() or "disconnected" in resp.json()["detail"].lower()

        db_session.refresh(conn)
        assert conn.connection_status == "disconnected"
        assert conn.connection_error is not None

    def test_sync_other_simplefin_error_marks_error_and_returns_422(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(
            db_session, user_id=test_user.id,
            provider_account_id="https://bridge.simplefin.org/simplefin/accounts/acct002",
        )

        mock_provider = MagicMock()
        mock_provider.list_transactions.side_effect = SimpleFINError("Unexpected SimpleFIN error")

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 422

        db_session.refresh(conn)
        assert conn.connection_status == "error"

    def test_successful_sync_resets_connection_status(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(
            db_session,
            user_id=test_user.id,
            provider_account_id="https://bridge.simplefin.org/simplefin/accounts/acct003",
            connection_status="disconnected",
        )
        conn.connection_error = "Previous error"
        db_session.commit()

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [_make_external_txn("txn_reset_001")]

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["added"] == 1

        db_session.refresh(conn)
        assert conn.connection_status == "connected"
        assert conn.connection_error is None


# ---------------------------------------------------------------------------
# Re-connect via SimpleFIN setup token
# ---------------------------------------------------------------------------

class TestReconnect:
    def test_exact_match_updates_row_on_reconnect(self, client, auth_headers, db_session, test_user):
        """Reconnecting with a new setup token updates the existing row's access URL."""
        acct_id = "https://bridge.simplefin.org/simplefin/accounts/stable_001"
        existing = _make_connection(
            db_session,
            user_id=test_user.id,
            provider_account_id=acct_id,
            token="https://olduser:oldpass@beta-bridge.simplefin.org/simplefin",
        )
        new_access_url = "https://newuser:newpass@beta-bridge.simplefin.org/simplefin"

        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [
            _make_external_account(account_id=acct_id, name="Updated HSA Name")
        ]

        with patch("app.api.v1.endpoints.bank.claim_simplefin_setup_token", return_value=new_access_url), \
             patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"setup_token": "aHR0cHM6Ly9leGFtcGxlLmNvbS9jbGFpbQ=="},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        accounts = resp.json()
        assert len(accounts) == 1
        # Same UUID — the original row was reused
        assert accounts[0]["id"] == str(existing.id)
        # Updated fields
        assert accounts[0]["account_name"] == "Updated HSA Name"
        assert accounts[0]["connection_status"] == "connected"

        db_session.refresh(existing)
        assert existing.enrollment_token == new_access_url

    def test_connect_creates_new_row_for_new_account(self, client, auth_headers, db_session, test_user):
        new_access_url = "https://u:p@beta-bridge.simplefin.org/simplefin"
        new_acct_id = "https://bridge.simplefin.org/simplefin/accounts/brand_new"

        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [
            _make_external_account(account_id=new_acct_id, name="New HSA")
        ]

        with patch("app.api.v1.endpoints.bank.claim_simplefin_setup_token", return_value=new_access_url), \
             patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"setup_token": "aHR0cHM6Ly9leGFtcGxlLmNvbS9jbGFpbQ=="},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        accounts = resp.json()
        assert len(accounts) == 1
        assert accounts[0]["account_name"] == "New HSA"
        assert accounts[0]["connection_status"] == "connected"

        count = db_session.query(BankConnection).filter(
            BankConnection.provider_account_id == new_acct_id
        ).count()
        assert count == 1

    def test_connect_invalid_setup_token_returns_422(self, client, auth_headers):
        with patch("app.api.v1.endpoints.bank.claim_simplefin_setup_token",
                   side_effect=SimpleFINError("not valid base64")):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"setup_token": "not-valid-base64!!!"},
                headers=auth_headers,
            )
        assert resp.status_code == 422

    def test_connect_already_claimed_token_returns_400(self, client, auth_headers):
        with patch("app.api.v1.endpoints.bank.claim_simplefin_setup_token",
                   side_effect=SimpleFINAuthError("already been claimed")):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"setup_token": "aHR0cHM6Ly9leGFtcGxlLmNvbS9jbGFpbQ=="},
                headers=auth_headers,
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Sync All
# ---------------------------------------------------------------------------

class TestSyncAll:
    def test_sync_all_returns_per_account_outcomes(self, client, auth_headers, db_session, test_user):
        _good = _make_connection(
            db_session, user_id=test_user.id,
            provider_account_id="https://bridge.simplefin.org/simplefin/accounts/good",
            token="https://u:p@bridge.com/good",
        )
        bad = _make_connection(
            db_session, user_id=test_user.id,
            provider_account_id="https://bridge.simplefin.org/simplefin/accounts/bad",
            token="https://u:p@bridge.com/bad",
        )

        def provider_factory(access_url):
            mock = MagicMock()
            if "good" in access_url:
                mock.list_transactions.return_value = [_make_external_txn("txn_all_001")]
            else:
                mock.list_transactions.side_effect = SimpleFINAuthError("expired")
            return mock

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", side_effect=provider_factory):
            resp = client.post("/api/v1/bank/accounts/sync-all", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        ok_outcomes = [o for o in data["outcomes"] if o["status"] == "ok"]
        fail_outcomes = [o for o in data["outcomes"] if o["status"] == "disconnected"]
        assert len(ok_outcomes) == 1
        assert len(fail_outcomes) == 1
        assert ok_outcomes[0]["added"] == 1

        db_session.refresh(bad)
        assert bad.connection_status == "disconnected"

    def test_sync_all_skips_already_disconnected_accounts(self, client, auth_headers, db_session, test_user):
        _make_connection(
            db_session, user_id=test_user.id,
            provider_account_id="https://bridge.simplefin.org/simplefin/accounts/skip_good",
        )
        _make_connection(
            db_session, user_id=test_user.id,
            provider_account_id="https://bridge.simplefin.org/simplefin/accounts/skip_bad",
            connection_status="disconnected",
        )

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = []

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post("/api/v1/bank/accounts/sync-all", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        # Only the connected account is attempted
        assert data["total"] == 1

    def test_sync_all_requires_auth(self, client):
        assert client.post("/api/v1/bank/accounts/sync-all").status_code == 401
