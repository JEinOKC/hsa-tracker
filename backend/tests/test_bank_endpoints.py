"""Integration tests for bank integration endpoints.

Teller API calls are mocked throughout — we test our HTTP layer,
DB operations, auth guards, and error handling, not Teller's servers.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.bank import BankConnection, BankTransaction
from app.providers.base import ExternalAccount, ExternalBalance, ExternalTransaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_external_account(account_id="acct_001", name="HSA Checking", subtype="hsa"):
    return ExternalAccount(
        id=account_id,
        name=name,
        type="depository",
        subtype=subtype,
        currency="USD",
        institution_name="First National Bank",
        provider="teller",
        last_four="1234",
    )


def _make_external_txn(txn_id="txn_001", amount="-50.00", status="posted"):
    return ExternalTransaction(
        id=txn_id,
        account_id="acct_001",
        date=date(2026, 3, 1),
        description="CVS Pharmacy",
        amount=Decimal(amount),
        type="card_payment",
        status=status,
        provider="teller",
        details={},
    )


def _make_connection(
    db_session,
    user_id=None,
    provider_account_id="acct_001",
    token="tok_abc",
    account_type="depository",
    account_subtype="hsa",
    account_name="HSA Checking",
):
    conn = BankConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="teller",
        provider_account_id=provider_account_id,
        account_name=account_name,
        account_type=account_type,
        account_subtype=account_subtype,
        institution_name="First National Bank",
        last_four="1234",
        currency="USD",
        enrollment_token=token,
        is_active=True,
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)
    return conn


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestBankAuthRequired:
    def test_status_requires_auth(self, client):
        assert client.get("/api/v1/bank/status").status_code == 403

    def test_connect_requires_auth(self, client):
        assert client.post("/api/v1/bank/connect", json={"access_token": "tok"}).status_code == 403

    def test_list_accounts_requires_auth(self, client):
        assert client.get("/api/v1/bank/accounts").status_code == 403

    def test_sync_requires_auth(self, client):
        assert client.post(f"/api/v1/bank/accounts/{uuid.uuid4()}/sync").status_code == 403


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class TestBankStatus:
    def test_reports_not_configured(self, client, auth_headers):
        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=False):
            resp = client.get("/api/v1/bank/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["teller_configured"] is False
        assert data["active_connections"] == 0

    def test_reports_configured_with_connection_count(self, client, auth_headers, db_session):
        _make_connection(db_session)
        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True):
            resp = client.get("/api/v1/bank/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["teller_configured"] is True
        assert data["active_connections"] == 1

    def test_inactive_connections_excluded_from_count(self, client, auth_headers, db_session):
        conn = _make_connection(db_session)
        conn.is_active = False
        db_session.commit()

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True):
            resp = client.get("/api/v1/bank/status", headers=auth_headers)
        assert resp.json()["active_connections"] == 0


# ---------------------------------------------------------------------------
# Connect (Teller enrollment)
# ---------------------------------------------------------------------------

class TestBankConnect:
    def test_connect_creates_accounts(self, client, auth_headers, db_session):
        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [_make_external_account()]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"access_token": "tok_abc"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        accounts = resp.json()
        assert len(accounts) == 1
        assert accounts[0]["provider_account_id"] == "acct_001"
        assert accounts[0]["account_name"] == "HSA Checking"
        assert accounts[0]["institution_name"] == "First National Bank"
        assert accounts[0]["last_four"] == "1234"

        # Token stored in DB
        conn = db_session.query(BankConnection).filter(
            BankConnection.provider_account_id == "acct_001"
        ).first()
        assert conn is not None
        assert conn.enrollment_token == "tok_abc"

    def test_connect_updates_existing_account(self, client, auth_headers, db_session):
        existing = _make_connection(db_session, token="old_tok")

        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [
            _make_external_account(name="HSA Checking Updated")
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
        assert existing.account_name == "HSA Checking Updated"
        assert existing.enrollment_token == "new_tok"

        # No duplicate rows
        count = db_session.query(BankConnection).filter(
            BankConnection.provider_account_id == "acct_001"
        ).count()
        assert count == 1

    def test_connect_returns_503_when_not_configured(self, client, auth_headers):
        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=False):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"access_token": "tok"},
                headers=auth_headers,
            )
        assert resp.status_code == 503

    def test_connect_uses_access_token_for_provider(self, client, auth_headers):
        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = []

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider) as mock_factory:
            client.post(
                "/api/v1/bank/connect",
                json={"access_token": "tok_xyz"},
                headers=auth_headers,
            )
        mock_factory.assert_called_once_with(access_token="tok_xyz")


# ---------------------------------------------------------------------------
# List accounts
# ---------------------------------------------------------------------------

class TestListBankAccounts:
    def test_returns_active_accounts(self, client, auth_headers, db_session, test_user):
        _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_001")
        _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_002")

        resp = client.get("/api/v1/bank/accounts", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_excludes_inactive_accounts(self, client, auth_headers, db_session, test_user):
        active = _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_active")
        inactive = _make_connection(db_session, user_id=test_user.id, provider_account_id="acct_inactive")
        inactive.is_active = False
        db_session.commit()

        resp = client.get("/api/v1/bank/accounts", headers=auth_headers)
        ids = [a["provider_account_id"] for a in resp.json()]
        assert "acct_active" in ids
        assert "acct_inactive" not in ids

    def test_returns_empty_when_no_accounts(self, client, auth_headers):
        resp = client.get("/api/v1/bank/accounts", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Get account detail
# ---------------------------------------------------------------------------

class TestGetBankAccount:
    def test_returns_account_with_live_balance(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.get_balance.return_value = ExternalBalance(
            account_id="acct_001",
            ledger=Decimal("4250.00"),
            available=Decimal("4250.00"),
            currency="USD",
        )

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.get(f"/api/v1/bank/accounts/{conn.id}", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["balance_ledger"] == "4250.00"
        assert data["balance_available"] == "4250.00"

    def test_returns_account_without_balance_on_provider_error(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.get_balance.side_effect = Exception("Teller unavailable")

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.get(f"/api/v1/bank/accounts/{conn.id}", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["balance_ledger"] is None

    def test_returns_404_for_unknown_account(self, client, auth_headers):
        resp = client.get(f"/api/v1/bank/accounts/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

class TestSyncAccount:
    def test_sync_stores_new_transactions(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [
            _make_external_txn("txn_001"),
            _make_external_txn("txn_002", amount="-25.00"),
        ]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["added"] == 2
        assert data["skipped"] == 0

        txns = db_session.query(BankTransaction).filter(
            BankTransaction.connection_id == conn.id
        ).all()
        assert len(txns) == 2

    def test_sync_skips_duplicates(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)
        # Pre-insert one transaction
        existing = BankTransaction(
            id=uuid.uuid4(),
            connection_id=conn.id,
            provider="teller",
            provider_transaction_id="txn_001",
            transaction_date=date(2026, 3, 1),
            description="Existing",
            amount=Decimal("-50.00"),
            status="posted",
        )
        db_session.add(existing)
        db_session.commit()

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [
            _make_external_txn("txn_001"),   # duplicate
            _make_external_txn("txn_002"),   # new
        ]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        data = resp.json()
        assert data["added"] == 1
        assert data["skipped"] == 1

    def test_sync_updates_last_synced_at(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)
        assert conn.last_synced_at is None

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = []

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        db_session.refresh(conn)
        assert conn.last_synced_at is not None

    def test_sync_returns_503_when_not_configured(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)
        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=False):
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)
        assert resp.status_code == 503

    def test_sync_returns_422_when_no_enrollment_token(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id, token=None)
        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True):
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)
        assert resp.status_code == 422

    def test_sync_returns_404_for_unknown_account(self, client, auth_headers):
        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True):
            resp = client.post(f"/api/v1/bank/accounts/{uuid.uuid4()}/sync", headers=auth_headers)
        assert resp.status_code == 404

    def test_sync_passes_enrollment_token_to_provider(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id, token="my_secret_token")

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = []

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider) as mock_factory:
            client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        mock_factory.assert_called_once_with(access_token="my_secret_token")

    # ------------------------------------------------------------------
    # Amount sign normalisation — regression for Teller credit accounts
    # ------------------------------------------------------------------

    def test_sync_depository_amount_stored_as_is(self, client, auth_headers, db_session, test_user):
        """Depository accounts: Teller sign convention matches ours (negative = debit)."""
        conn = _make_connection(db_session, user_id=test_user.id, account_type="depository")

        mock_provider = MagicMock()
        # Teller sends a debit as negative on depository accounts
        mock_provider.list_transactions.return_value = [
            _make_external_txn("txn_dep_debit", amount="-42.00"),
        ]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        txn = db_session.query(BankTransaction).filter(
            BankTransaction.connection_id == conn.id
        ).one()
        assert txn.amount == Decimal("-42.00")

    def test_sync_credit_account_purchase_stored_as_negative(self, client, auth_headers, db_session, test_user):
        """Credit accounts: Teller sends purchases as positive; we must negate so they show as expenses."""
        conn = _make_connection(
            db_session,
            user_id=test_user.id,
            account_type="credit",
            account_subtype="credit_card",
            account_name="Chase Sapphire",
        )

        mock_provider = MagicMock()
        # Teller sends a credit-card purchase as +26.04 (increases balance owed)
        mock_provider.list_transactions.return_value = [
            _make_external_txn("txn_cc_purchase", amount="26.04"),
        ]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        txn = db_session.query(BankTransaction).filter(
            BankTransaction.connection_id == conn.id
        ).one()
        # Must be stored as negative so the UI renders it as an expense (red)
        assert txn.amount == Decimal("-26.04")

    def test_sync_credit_account_payment_stored_as_positive(self, client, auth_headers, db_session, test_user):
        """Credit accounts: Teller sends card payments as negative; we negate so they show as credits."""
        conn = _make_connection(
            db_session,
            user_id=test_user.id,
            account_type="credit",
            account_subtype="credit_card",
            account_name="Chase Sapphire",
        )

        mock_provider = MagicMock()
        # Teller sends a payment to the card as -200.00 (decreases balance owed)
        mock_provider.list_transactions.return_value = [
            _make_external_txn("txn_cc_payment", amount="-200.00"),
        ]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider):
            client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        txn = db_session.query(BankTransaction).filter(
            BankTransaction.connection_id == conn.id
        ).one()
        # Must be stored as positive so the UI renders it as a credit (green)
        assert txn.amount == Decimal("200.00")


# ---------------------------------------------------------------------------
# List transactions
# ---------------------------------------------------------------------------

class TestListBankTransactions:
    @pytest.fixture
    def conn_with_txns(self, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)
        txns = [
            BankTransaction(
                id=uuid.uuid4(),
                connection_id=conn.id,
                provider="teller",
                provider_transaction_id=f"txn_{i:03d}",
                transaction_date=date(2026, i % 12 + 1, 1),
                description=f"Transaction {i}",
                amount=Decimal(f"-{i * 10}.00"),
                status="posted" if i % 2 == 0 else "pending",
            )
            for i in range(1, 6)
        ]
        for t in txns:
            db_session.add(t)
        db_session.commit()
        return conn

    def test_returns_all_transactions(self, client, auth_headers, conn_with_txns):
        resp = client.get(
            f"/api/v1/bank/accounts/{conn_with_txns.id}/transactions",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    def test_filters_by_status(self, client, auth_headers, conn_with_txns):
        resp = client.get(
            f"/api/v1/bank/accounts/{conn_with_txns.id}/transactions?status=posted",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        statuses = {t["status"] for t in resp.json()}
        assert statuses == {"posted"}

    def test_respects_limit(self, client, auth_headers, conn_with_txns):
        resp = client.get(
            f"/api/v1/bank/accounts/{conn_with_txns.id}/transactions?limit=2",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_returns_404_for_unknown_account(self, client, auth_headers):
        resp = client.get(
            f"/api/v1/bank/accounts/{uuid.uuid4()}/transactions",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------

class TestDisconnectAccount:
    def test_deactivates_connection(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)
        resp = client.delete(f"/api/v1/bank/accounts/{conn.id}", headers=auth_headers)
        assert resp.status_code == 204

        db_session.refresh(conn)
        assert conn.is_active is False

    def test_preserves_transactions_after_disconnect(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)
        txn = BankTransaction(
            id=uuid.uuid4(),
            connection_id=conn.id,
            provider="teller",
            provider_transaction_id="txn_keep",
            transaction_date=date(2026, 1, 1),
            description="Keep me",
            amount=Decimal("-10.00"),
            status="posted",
        )
        db_session.add(txn)
        db_session.commit()

        client.delete(f"/api/v1/bank/accounts/{conn.id}", headers=auth_headers)

        still_there = db_session.query(BankTransaction).filter(
            BankTransaction.provider_transaction_id == "txn_keep"
        ).first()
        assert still_there is not None

    def test_returns_404_for_unknown_account(self, client, auth_headers):
        resp = client.delete(f"/api/v1/bank/accounts/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sync — push notification on potential HSA transactions
# ---------------------------------------------------------------------------

class TestSyncPushNotification:
    def test_potential_hsa_count_zero_when_none_flagged(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [
            _make_external_txn("txn_001"),
        ]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider), \
             patch("app.api.v1.endpoints.bank.apply_auto_flag") as mock_flag:
            # apply_auto_flag does nothing (no flag set)
            mock_flag.return_value = None
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["potential_hsa_count"] == 0

    def test_potential_hsa_count_matches_flagged_transactions(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [
            _make_external_txn("txn_001"),
            _make_external_txn("txn_002", amount="-30.00"),
        ]

        def flag_first_only(txn):
            if txn.provider_transaction_id == "txn_001":
                txn.auto_flag = "potential_hsa"

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider), \
             patch("app.api.v1.endpoints.bank.apply_auto_flag", side_effect=flag_first_only), \
             patch("app.api.v1.endpoints.bank.send_push_to_user"):
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["potential_hsa_count"] == 1

    def test_push_sent_with_singular_body_and_review_url(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [_make_external_txn("txn_001")]

        def flag_all(txn):
            txn.auto_flag = "potential_hsa"

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider), \
             patch("app.api.v1.endpoints.bank.apply_auto_flag", side_effect=flag_all), \
             patch("app.api.v1.endpoints.bank.send_push_to_user") as mock_push:
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        assert resp.status_code == 200
        mock_push.assert_called_once()
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["body"] == "1 new transaction may be HSA-eligible"
        assert call_kwargs["url"] == "/review"

    def test_push_sent_with_plural_body_for_multiple(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [
            _make_external_txn("txn_001"),
            _make_external_txn("txn_002", amount="-30.00"),
        ]

        def flag_all(txn):
            txn.auto_flag = "potential_hsa"

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider), \
             patch("app.api.v1.endpoints.bank.apply_auto_flag", side_effect=flag_all), \
             patch("app.api.v1.endpoints.bank.send_push_to_user") as mock_push:
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        assert resp.status_code == 200
        mock_push.assert_called_once()
        assert mock_push.call_args.kwargs["body"] == "2 new transactions may be HSA-eligible"

    def test_push_not_sent_when_no_potential_hsa(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [_make_external_txn("txn_001")]

        with patch("app.api.v1.endpoints.bank.is_teller_configured", return_value=True), \
             patch("app.api.v1.endpoints.bank.get_teller_provider", return_value=mock_provider), \
             patch("app.api.v1.endpoints.bank.apply_auto_flag"), \
             patch("app.api.v1.endpoints.bank.send_push_to_user") as mock_push:
            resp = client.post(f"/api/v1/bank/accounts/{conn.id}/sync", headers=auth_headers)

        assert resp.status_code == 200
        mock_push.assert_not_called()
