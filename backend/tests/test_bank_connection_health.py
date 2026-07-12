"""Tests for bank connection health tracking, error handling, and seamless re-connect.

Covers:
- Sync marks connection as 'disconnected' on Teller 404/401
- Sync marks connection as 'error' on other Teller errors
- Successful sync resets connection_status to 'connected'
- Re-connect fuzzy match reuses existing row (preserves transaction history)
- Re-connect exact match still works
- sync-all returns per-account outcomes
- sync-all skips already-disconnected accounts
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.models.bank import BankConnection, BankTransaction
from app.providers.base import ExternalAccount, ExternalTransaction
from app.providers.teller.client import (
    TellerAPIError,
    TellerAuthError,
    TellerDisconnectedError,
)

# ---------------------------------------------------------------------------
# Helpers (mirror test_bank_endpoints.py patterns)
# ---------------------------------------------------------------------------

def _make_connection(
    db_session,
    user_id=None,
    provider_account_id="acct_health_001",
    token="tok_health",
    account_type="depository",
    account_subtype="hsa",
    account_name="HSA Checking",
    institution_name="First National Bank",
    last_four="1234",
    connection_status="connected",
):
    conn = BankConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="teller",
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
    account_id="acct_health_001",
    name="HSA Checking",
    subtype="hsa",
    institution_name="First National Bank",
    last_four="1234",
):
    return ExternalAccount(
        id=account_id,
        name=name,
        type="depository",
        subtype=subtype,
        currency="USD",
        institution_name=institution_name,
        provider="teller",
        last_four=last_four,
    )


def _make_external_txn(txn_id="txn_health_001", amount="-50.00"):
    return ExternalTransaction(
        id=txn_id,
        account_id="acct_health_001",
        date=date(2026, 3, 1),
        description="CVS Pharmacy",
        amount=Decimal(amount),
        type="card_payment",
        status="posted",
        provider="teller",
        details={},
    )


# ---------------------------------------------------------------------------
# Sync error handling
# ---------------------------------------------------------------------------

class TestSyncConnectionErrors:
    def test_sync_404_marks_disconnected_and_returns_409(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.side_effect = TellerDisconnectedError(
            "Teller returned 404 for /accounts/acct_health_001/transactions. Account or enrollment no longer exists.",
            status_code=404,
        )

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 409
        assert "disconnected" in resp.json()["detail"].lower()

        db_session.refresh(conn)
        assert conn.connection_status == "disconnected"
        assert conn.connection_error is not None
        assert "404" in conn.connection_error

    def test_sync_401_marks_disconnected_and_returns_409(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_health_002")

        mock_provider = MagicMock()
        mock_provider.list_transactions.side_effect = TellerAuthError(
            "Teller returned 401 for /accounts/acct_health_002/transactions. Enrollment token is invalid or revoked.",
            status_code=401,
        )

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 409
        assert "token" in resp.json()["detail"].lower() or "enrollment" in resp.json()["detail"].lower()

        db_session.refresh(conn)
        assert conn.connection_status == "disconnected"
        assert conn.connection_error is not None
        assert "401" in conn.connection_error

    def test_sync_other_teller_error_marks_error_and_returns_422(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_health_003")

        mock_provider = MagicMock()
        mock_provider.list_transactions.side_effect = TellerAPIError(
            "Teller returned 500: internal server error",
            status_code=500,
        )

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
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
            provider_account_id="acct_health_004",
            connection_status="disconnected",
        )
        conn.connection_error = "Previous error"
        db_session.commit()

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [_make_external_txn("txn_reset_001")]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
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
# Seamless re-connect
# ---------------------------------------------------------------------------

class TestSeamlessReconnect:
    def test_fuzzy_match_reuses_existing_row_on_reconnect(self, client, auth_headers, db_session, test_user):
        """Re-enrolling returns a new provider_account_id but same institution+last_four+subtype.
        The endpoint should reuse the existing DB row instead of creating a duplicate."""
        original = _make_connection(
            db_session,
            user_id=test_user.id,
            provider_account_id="acct_OLD_001",
            connection_status="disconnected",
            institution_name="American Express",
            last_four="9999",
            account_subtype="credit_card",
            account_type="credit",
            account_name="Amex Gold",
        )
        original_id = original.id

        # Add a transaction to verify history is preserved
        txn = BankTransaction(
            id=uuid.uuid4(),
            connection_id=original.id,
            provider="teller",
            provider_transaction_id="txn_old_001",
            transaction_date=date(2026, 1, 15),
            description="Old transaction",
            amount=Decimal("-100.00"),
            transaction_type="card_payment",
            status="posted",
            source="teller",
        )
        db_session.add(txn)
        db_session.commit()

        # New enrollment returns a new account ID
        new_acct = _make_external_account(
            account_id="acct_NEW_999",
            name="Amex Gold Card",
            subtype="credit_card",
            institution_name="American Express",
            last_four="9999",
        )
        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [new_acct]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"access_token": "new_token_999"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        accounts = resp.json()
        assert len(accounts) == 1
        # Same UUID — the original row was reused
        assert accounts[0]["id"] == str(original_id)
        # Provider account ID updated to the new one
        assert accounts[0]["provider_account_id"] == "acct_NEW_999"
        # Status reset
        assert accounts[0]["connection_status"] == "connected"

        # Old transaction still present
        txn_count = db_session.query(BankTransaction).filter(
            BankTransaction.connection_id == original_id
        ).count()
        assert txn_count == 1

        # No duplicate connection row
        total = db_session.query(BankConnection).filter(
            BankConnection.institution_name == "American Express",
            BankConnection.last_four == "9999",
        ).count()
        assert total == 1

    def test_exact_match_still_works_after_fuzzy_logic_added(self, client, auth_headers, db_session, test_user):
        """Existing exact-match path (same provider_account_id) must still update the row."""
        existing = _make_connection(
            db_session,
            user_id=test_user.id,
            provider_account_id="acct_exact_001",
            token="old_tok",
        )
        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [
            _make_external_account(account_id="acct_exact_001", name="Updated Name")
        ]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"access_token": "new_tok"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        db_session.refresh(existing)
        assert existing.account_name == "Updated Name"
        assert existing.enrollment_token == "new_tok"
        assert existing.connection_status == "connected"

        count = db_session.query(BankConnection).filter(
            BankConnection.provider_account_id == "acct_exact_001"
        ).count()
        assert count == 1


# ---------------------------------------------------------------------------
# Sync All
# ---------------------------------------------------------------------------

class TestSyncAll:
    def test_sync_all_returns_per_account_outcomes(self, client, auth_headers, db_session, test_user):
        _good = _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_all_good", token="tok_good")
        bad = _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_all_bad", token="tok_bad")

        def provider_factory(access_token):
            mock = MagicMock()
            if access_token == "tok_good":
                mock.list_transactions.return_value = [_make_external_txn("txn_all_001")]
            else:
                mock.list_transactions.side_effect = TellerDisconnectedError(
                    "Teller returned 404", status_code=404
                )
            return mock

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", side_effect=provider_factory):
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

        # Bad connection marked in DB
        db_session.refresh(bad)
        assert bad.connection_status == "disconnected"

    def test_sync_all_skips_already_disconnected_accounts(self, client, auth_headers, db_session, test_user):
        _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_skip_good")
        _make_connection(
            db_session, user_id=test_user.id,
            provider_account_id="acct_skip_bad",
            connection_status="disconnected",
        )

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = []

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.post("/api/v1/bank/accounts/sync-all", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        # Only the connected account is attempted
        assert data["total"] == 1

    def test_sync_all_returns_503_when_not_configured(self, client, auth_headers):
        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=False):
            resp = client.post("/api/v1/bank/accounts/sync-all", headers=auth_headers)
        assert resp.status_code == 503

    def test_sync_all_requires_auth(self, client):
        assert client.post("/api/v1/bank/accounts/sync-all").status_code == 401
