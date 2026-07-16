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

    def test_connect_saves_access_url_before_discovery(self, client, auth_headers, db_session, test_user):
        """If account discovery fails after claiming, the access URL is still persisted."""
        acct_id = "https://bridge.simplefin.org/simplefin/accounts/saved_001"
        existing = _make_connection(
            db_session,
            user_id=test_user.id,
            provider_account_id=acct_id,
            token="https://old:old@bridge.simplefin.org/simplefin",
            connection_status="disconnected",
        )
        new_access_url = "https://new:new@beta-bridge.simplefin.org/simplefin"

        mock_provider = MagicMock()
        mock_provider.list_accounts.side_effect = Exception("network blew up")

        with patch("app.api.v1.endpoints.bank.claim_simplefin_setup_token", return_value=new_access_url), \
             patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"setup_token": "aHR0cHM6Ly9leGFtcGxlLmNvbS9jbGFpbQ=="},
                headers=auth_headers,
            )

        assert resp.status_code == 502
        assert "claimed successfully" in resp.json()["detail"]

        # The access URL was saved despite the failure
        db_session.refresh(existing)
        assert existing.enrollment_token == new_access_url
        assert existing.connection_status == "connected"

    def test_connect_discovery_fail_creates_placeholder_for_new_user(self, client, auth_headers, db_session, test_user):
        """If there are no existing connections and discovery fails, a placeholder is created."""
        new_access_url = "https://new:new@beta-bridge.simplefin.org/simplefin"

        mock_provider = MagicMock()
        mock_provider.list_accounts.side_effect = Exception("timeout")

        with patch("app.api.v1.endpoints.bank.claim_simplefin_setup_token", return_value=new_access_url), \
             patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"setup_token": "aHR0cHM6Ly9leGFtcGxlLmNvbS9jbGFpbQ=="},
                headers=auth_headers,
            )

        assert resp.status_code == 502

        placeholder = db_session.query(BankConnection).filter(
            BankConnection.user_id == test_user.id,
            BankConnection.provider == "simplefin",
        ).first()
        assert placeholder is not None
        assert placeholder.enrollment_token == new_access_url

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


# ---------------------------------------------------------------------------
# Cross-provider matching (Teller → SimpleFIN migration)
# ---------------------------------------------------------------------------


class TestCrossProviderMatching:
    def test_connect_matches_by_last_four_when_no_simplefin_match(self, client, auth_headers, db_session, test_user):
        """A Teller connection with matching last4 is updated in-place."""
        teller_conn = _make_connection(
            db_session,
            user_id=test_user.id,
            provider_account_id="teller_acct_4321",
            account_type="credit",
            account_subtype="credit_card",
            account_name="Rewards Card",
            institution_name="Test Bank",
            last_four="4321",
        )
        teller_conn.provider = "teller"
        db_session.commit()

        new_access_url = "https://u:p@beta-bridge.simplefin.org/simplefin"
        sf_acct_id = "https://bridge.simplefin.org/simplefin/accounts/rewards4321"

        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [
            _make_external_account(
                account_id=sf_acct_id,
                name="Rewards Card (4321)",
                institution_name="Test Bank",
                last_four="4321",
            )
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
        # Same UUID — the Teller row was reused
        assert accounts[0]["id"] == str(teller_conn.id)
        # Provider identity updated
        assert accounts[0]["connection_status"] == "connected"
        assert accounts[0]["account_name"] == "Rewards Card (4321)"

        db_session.refresh(teller_conn)
        assert teller_conn.provider == "simplefin"
        assert teller_conn.provider_account_id == sf_acct_id
        assert teller_conn.enrollment_token == new_access_url

    def test_cross_provider_match_preserves_account_type(self, client, auth_headers, db_session, test_user):
        """SimpleFIN wrongly reports credit cards as depository/checking.
        Cross-provider match must keep the original account_type/subtype."""
        teller_conn = _make_connection(
            db_session,
            user_id=test_user.id,
            provider_account_id="teller_acct_5678",
            account_type="credit",
            account_subtype="credit_card",
            account_name="Travel Rewards Card",
            last_four="5678",
        )
        teller_conn.provider = "teller"
        db_session.commit()

        new_access_url = "https://u:p@beta-bridge.simplefin.org/simplefin"

        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [
            _make_external_account(
                account_id="https://bridge.simplefin.org/simplefin/accounts/travel5678",
                name="Travel Rewards Card (5678)",
                subtype="checking",  # SimpleFIN always says checking
                last_four="5678",
            )
        ]

        with patch("app.api.v1.endpoints.bank.claim_simplefin_setup_token", return_value=new_access_url), \
             patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/bank/connect",
                json={"setup_token": "aHR0cHM6Ly9leGFtcGxlLmNvbS9jbGFpbQ=="},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        db_session.refresh(teller_conn)
        # Type preserved from Teller — NOT overwritten with SimpleFIN's "depository/checking"
        assert teller_conn.account_type == "credit"
        assert teller_conn.account_subtype == "credit_card"

    def test_no_match_creates_new_connection(self, client, auth_headers, db_session, test_user):
        """SimpleFIN accounts with no Teller match create new connections."""
        new_access_url = "https://u:p@beta-bridge.simplefin.org/simplefin"
        sf_acct_id = "https://bridge.simplefin.org/simplefin/accounts/newacct8765"

        mock_provider = MagicMock()
        mock_provider.list_accounts.return_value = [
            _make_external_account(
                account_id=sf_acct_id,
                name="Auto Loan (8765)",
                last_four="8765",
            )
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
        assert accounts[0]["account_name"] == "Auto Loan (8765)"

        count = db_session.query(BankConnection).filter(
            BankConnection.provider_account_id == sf_acct_id
        ).count()
        assert count == 1


# ---------------------------------------------------------------------------
# Overlap-window dedup (Teller → SimpleFIN sync)
# ---------------------------------------------------------------------------


class TestOverlapWindowDedup:
    def test_sync_skips_simplefin_txns_before_teller_cutoff(self, client, auth_headers, db_session, test_user):
        """SimpleFIN transactions before (latest_teller - 2 days) are skipped."""
        from app.models.bank import BankTransaction

        conn = _make_connection(db_session, user_id=test_user.id)

        # Add a Teller transaction on 2026-07-07
        teller_txn = BankTransaction(
            connection_id=conn.id,
            source="teller",
            provider="teller",
            provider_transaction_id="teller_txn_001",
            transaction_date=date(2026, 7, 7),
            description="Some purchase",
            amount=Decimal("-50.00"),
            status="posted",
        )
        db_session.add(teller_txn)
        db_session.commit()

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [
            _make_external_txn("sf_old", "-30.00"),  # default date 2026-03-01 — before cutoff
        ]

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["added"] == 0

    def test_sync_imports_simplefin_txns_after_teller_cutoff(self, client, auth_headers, db_session, test_user):
        """SimpleFIN transactions well after the Teller cutoff are imported."""
        from app.models.bank import BankTransaction

        conn = _make_connection(db_session, user_id=test_user.id)

        teller_txn = BankTransaction(
            connection_id=conn.id,
            source="teller",
            provider="teller",
            provider_transaction_id="teller_txn_002",
            transaction_date=date(2026, 5, 6),
            description="Teller purchase",
            amount=Decimal("-100.00"),
            status="posted",
        )
        db_session.add(teller_txn)
        db_session.commit()

        # SimpleFIN txn on 2026-05-15 — well after cutoff
        sf_txn = _make_external_txn("sf_new", "-23.20")
        sf_txn = ExternalTransaction(
            id="sf_new",
            account_id=conn.provider_account_id,
            date=date(2026, 5, 15),
            description="New purchase",
            amount=Decimal("-23.20"),
            type="",
            status="posted",
            provider="simplefin",
            details={},
        )

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [sf_txn]

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["added"] == 1

    def test_sync_dedupes_by_amount_in_overlap_window(self, client, auth_headers, db_session, test_user):
        """SimpleFIN txn with same amount as Teller txn within ±2 days is skipped."""
        from app.models.bank import BankTransaction

        conn = _make_connection(db_session, user_id=test_user.id)

        teller_txn = BankTransaction(
            connection_id=conn.id,
            source="teller",
            provider="teller",
            provider_transaction_id="teller_txn_003",
            transaction_date=date(2026, 7, 7),
            description="Local Restaurant",
            amount=Decimal("-28.17"),
            status="posted",
        )
        db_session.add(teller_txn)
        db_session.commit()

        # SimpleFIN has the same amount on the same date — should be skipped
        sf_dup = ExternalTransaction(
            id="sf_dup",
            account_id=conn.provider_account_id,
            date=date(2026, 7, 7),
            description="Local Restaurant",
            amount=Decimal("-28.17"),
            type="",
            status="posted",
            provider="simplefin",
            details={},
        )

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [sf_dup]

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["added"] == 0

    def test_sync_imports_unique_amount_on_boundary_date(self, client, auth_headers, db_session, test_user):
        """SimpleFIN txn on the Teller cutoff date with a different amount is imported."""
        from app.models.bank import BankTransaction

        conn = _make_connection(db_session, user_id=test_user.id)

        teller_txn = BankTransaction(
            connection_id=conn.id,
            source="teller",
            provider="teller",
            provider_transaction_id="teller_txn_004",
            transaction_date=date(2026, 5, 6),
            description="Concert Tickets",
            amount=Decimal("-477.68"),
            status="posted",
        )
        db_session.add(teller_txn)
        db_session.commit()

        # SimpleFIN has a DIFFERENT amount on the same date — should be imported
        sf_unique = ExternalTransaction(
            id="sf_unique",
            account_id=conn.provider_account_id,
            date=date(2026, 5, 6),
            description="Grocery Store",
            amount=Decimal("-23.20"),
            type="",
            status="posted",
            provider="simplefin",
            details={},
        )

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [sf_unique]

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["added"] == 1

    def test_no_teller_txns_means_no_dedup(self, client, auth_headers, db_session, test_user):
        """Non-migrated connections (no Teller transactions) import everything."""
        conn = _make_connection(db_session, user_id=test_user.id)

        mock_provider = MagicMock()
        mock_provider.list_transactions.return_value = [
            _make_external_txn("sf_normal_001", "-50.00"),
            _make_external_txn("sf_normal_002", "-25.00"),
        ]

        with patch("app.api.v1.endpoints.bank.get_simplefin_provider", return_value=mock_provider):
            resp = client.post(
                f"/api/v1/bank/accounts/{conn.id}/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["added"] == 2
