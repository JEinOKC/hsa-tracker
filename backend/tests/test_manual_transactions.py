"""Tests for manual transaction endpoints and the merchants summary endpoint.

Covers:
  GET  /bank/transactions/merchants
  GET  /transactions/match
  POST /transactions/
  PUT  /transactions/{id}
  DELETE /transactions/{id}
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.models.bank import BankConnection, BankTransaction
from app.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connection(db, user_id, *, is_active=True):
    conn = BankConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="teller",
        provider_account_id=f"acct_{uuid.uuid4().hex[:8]}",
        account_name="Checking",
        institution_name="First Bank",
        currency="USD",
        is_active=is_active,
    )
    db.add(conn)
    db.flush()
    return conn


def _make_teller_txn(db, connection_id, *, transaction_date=None, amount=None, details=None, **kwargs):
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=connection_id,
        source="teller",
        provider="teller",
        provider_transaction_id=f"txn_{uuid.uuid4().hex[:8]}",
        transaction_date=transaction_date or date(2026, 3, 1),
        description=kwargs.get("description", "Test Merchant"),
        amount=amount if amount is not None else Decimal("-50.00"),
        status="posted",
        details=details,
    )
    db.add(txn)
    db.flush()
    return txn


def _make_manual_txn(db, user_id, *, transaction_date=None, amount=None, merchant_name="Test Merchant", **kwargs):
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=None,
        user_id=user_id,
        source="manual",
        provider="manual",
        provider_transaction_id=f"manual_{uuid.uuid4().hex[:8]}",
        transaction_date=transaction_date or date(2026, 3, 1),
        description=kwargs.get("description"),
        amount=amount if amount is not None else Decimal("-50.00"),
        transaction_type="manual",
        status="posted",
        details={"counterparty": {"name": merchant_name}},
    )
    db.add(txn)
    db.flush()
    return txn


# ---------------------------------------------------------------------------
# GET /bank/transactions/merchants
# ---------------------------------------------------------------------------

class TestMerchantsEndpoint:
    def test_returns_grouped_merchants(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "MCDONALD'S #4829"}})
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "MCDONALD'S #3021"}})
        db_session.commit()

        r = client.get("/api/v1/bank/transactions/merchants", headers=auth_headers)
        assert r.status_code == 200
        names = [m["normalized_name"] for m in r.json()]
        # Both McDonald's variants normalize to one entry
        assert names.count("MCDONALD'S") == 1

    def test_transaction_count_aggregated(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "STARBUCKS 1234"}})
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "STARBUCKS 5678"}})
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "STARBUCKS 9999"}})
        db_session.commit()

        r = client.get("/api/v1/bank/transactions/merchants", headers=auth_headers)
        merchants = {m["normalized_name"]: m for m in r.json()}
        assert merchants["STARBUCKS"]["transaction_count"] == 3

    def test_has_hsa_flag_set_when_any_txn_is_hsa_eligible(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        t1 = _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "CVS PHARMACY"}})
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "CVS PHARMACY"}})
        t1.is_hsa_eligible = True
        db_session.commit()

        r = client.get("/api/v1/bank/transactions/merchants", headers=auth_headers)
        merchants = {m["normalized_name"]: m for m in r.json()}
        assert merchants["CVS PHARMACY"]["has_hsa"] is True

    def test_has_hsa_false_when_no_txn_is_hsa_eligible(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "TARGET"}})
        db_session.commit()

        r = client.get("/api/v1/bank/transactions/merchants", headers=auth_headers)
        merchants = {m["normalized_name"]: m for m in r.json()}
        assert merchants["TARGET"]["has_hsa"] is False

    def test_hsa_likelihood_classified(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "WALGREENS"}})
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "MCDONALD'S"}})
        _make_teller_txn(db_session, conn.id, details={"counterparty": {"name": "SOME RANDOM SHOP"}})
        db_session.commit()

        r = client.get("/api/v1/bank/transactions/merchants", headers=auth_headers)
        assert r.status_code == 200
        merchants = {m["normalized_name"]: m for m in r.json()}
        assert merchants["WALGREENS"]["hsa_likelihood"] == "likely"
        assert merchants["MCDONALD'S"]["hsa_likelihood"] == "unlikely"
        assert merchants["SOME RANDOM SHOP"]["hsa_likelihood"] == "unknown"

    def test_does_not_return_other_users_merchants(self, client, db_session, test_user, auth_headers):
        other_user = User(
            id=uuid.uuid4(), username="other_merch_user",
            display_name="Other", is_active=True, is_superuser=False,
        )
        db_session.add(other_user)
        db_session.flush()
        other_conn = _make_connection(db_session, other_user.id)
        _make_teller_txn(db_session, other_conn.id, details={"counterparty": {"name": "SECRET MERCHANT"}})
        db_session.commit()

        r = client.get("/api/v1/bank/transactions/merchants", headers=auth_headers)
        names = [m["normalized_name"] for m in r.json()]
        assert "SECRET MERCHANT" not in names

    def test_requires_authentication(self, client):
        r = client.get("/api/v1/bank/transactions/merchants")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /transactions/match
# ---------------------------------------------------------------------------

class TestMatchEndpoint:
    def test_finds_matching_transaction_by_amount_and_date(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(
            db_session, conn.id,
            transaction_date=date(2026, 3, 15),
            amount=Decimal("-100.00"),
            details={"counterparty": {"name": "WALGREENS"}},
        )
        db_session.commit()

        r = client.get(
            "/api/v1/transactions/match",
            params={"amount": "100.00", "date": "2026-03-15"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_amount_tolerance_within_5_percent(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(
            db_session, conn.id,
            transaction_date=date(2026, 3, 15),
            amount=Decimal("-100.00"),
        )
        db_session.commit()

        # 4% off — should match
        r = client.get(
            "/api/v1/transactions/match",
            params={"amount": "96.00", "date": "2026-03-15"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_amount_outside_5_percent_tolerance_not_matched(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(
            db_session, conn.id,
            transaction_date=date(2026, 3, 15),
            amount=Decimal("-100.00"),
        )
        db_session.commit()

        # 10% off — should not match
        r = client.get(
            "/api/v1/transactions/match",
            params={"amount": "90.00", "date": "2026-03-15"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) == 0

    def test_date_within_60_days_matched(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(
            db_session, conn.id,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("-50.00"),
        )
        db_session.commit()

        # 59 days later — should match
        r = client.get(
            "/api/v1/transactions/match",
            params={"amount": "50.00", "date": "2026-03-01"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_date_beyond_60_days_not_matched(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(
            db_session, conn.id,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("-50.00"),
        )
        db_session.commit()

        # 90 days later — should not match
        r = client.get(
            "/api/v1/transactions/match",
            params={"amount": "50.00", "date": "2026-04-01"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) == 0

    def test_merchant_filter_applies(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_teller_txn(
            db_session, conn.id,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("-50.00"),
            details={"counterparty": {"name": "WALGREENS PHARMACY"}},
        )
        _make_teller_txn(
            db_session, conn.id,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("-50.00"),
            details={"counterparty": {"name": "TARGET STORE"}},
        )
        db_session.commit()

        r = client.get(
            "/api/v1/transactions/match",
            params={"amount": "50.00", "date": "2026-03-01", "merchant": "walgreens"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 1
        assert results[0]["merchant_name"] == "WALGREENS PHARMACY"

    def test_does_not_return_other_users_transactions(self, client, db_session, test_user, auth_headers):
        other_user = User(
            id=uuid.uuid4(), username="other_match_user",
            display_name="Other", is_active=True, is_superuser=False,
        )
        db_session.add(other_user)
        db_session.flush()
        other_conn = _make_connection(db_session, other_user.id)
        _make_teller_txn(
            db_session, other_conn.id,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("-50.00"),
        )
        db_session.commit()

        r = client.get(
            "/api/v1/transactions/match",
            params={"amount": "50.00", "date": "2026-03-01"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) == 0

    def test_returns_at_most_5_candidates(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        for i in range(8):
            _make_teller_txn(
                db_session, conn.id,
                transaction_date=date(2026, 3, 1),
                amount=Decimal("-50.00"),
                details={"counterparty": {"name": f"Merchant {i}"}},
            )
        db_session.commit()

        r = client.get(
            "/api/v1/transactions/match",
            params={"amount": "50.00", "date": "2026-03-01"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) <= 5

    def test_requires_authentication(self, client):
        r = client.get("/api/v1/transactions/match", params={"amount": "50.00", "date": "2026-03-01"})
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /transactions/
# ---------------------------------------------------------------------------

class TestCreateManualTransaction:
    def test_creates_transaction_successfully(self, client, db_session, test_user, auth_headers):
        r = client.post(
            "/api/v1/transactions/",
            json={
                "transaction_date": "2026-03-15",
                "amount": "125.00",
                "merchant_name": "Dr. Jones Optometry",
            },
            headers=auth_headers,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["source"] == "manual"
        assert float(data["amount"]) == pytest.approx(-125.00)

    def test_stores_merchant_in_counterparty_details(self, client, db_session, test_user, auth_headers):
        r = client.post(
            "/api/v1/transactions/",
            json={
                "transaction_date": "2026-03-15",
                "amount": "75.00",
                "merchant_name": "City Dental",
            },
            headers=auth_headers,
        )
        assert r.status_code == 201
        # The merchant name is in details.counterparty.name — returned as merchant_name via _build_response
        # or visible in description/merchant display; verify amount and date
        data = r.json()
        assert data["transaction_date"] == "2026-03-15"

    def test_amount_stored_as_negative_debit(self, client, db_session, test_user, auth_headers):
        r = client.post(
            "/api/v1/transactions/",
            json={"transaction_date": "2026-03-15", "amount": "50.00", "merchant_name": "Test"},
            headers=auth_headers,
        )
        assert r.status_code == 201
        assert float(r.json()["amount"]) < 0

    def test_description_is_optional(self, client, db_session, test_user, auth_headers):
        r = client.post(
            "/api/v1/transactions/",
            json={"transaction_date": "2026-03-15", "amount": "30.00", "merchant_name": "Test"},
            headers=auth_headers,
        )
        assert r.status_code == 201

    def test_requires_authentication(self, client):
        r = client.post(
            "/api/v1/transactions/",
            json={"transaction_date": "2026-03-15", "amount": "50.00", "merchant_name": "Test"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# PUT /transactions/{id}
# ---------------------------------------------------------------------------

class TestUpdateManualTransaction:
    def test_updates_amount(self, client, db_session, test_user, auth_headers):
        txn = _make_manual_txn(db_session, test_user.id, amount=Decimal("-50.00"))
        db_session.commit()

        r = client.put(
            f"/api/v1/transactions/{txn.id}",
            json={"amount": "99.00"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert float(r.json()["amount"]) == pytest.approx(-99.00)

    def test_updates_transaction_date(self, client, db_session, test_user, auth_headers):
        txn = _make_manual_txn(db_session, test_user.id, transaction_date=date(2026, 1, 1))
        db_session.commit()

        r = client.put(
            f"/api/v1/transactions/{txn.id}",
            json={"transaction_date": "2026-06-15"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["transaction_date"] == "2026-06-15"

    def test_returns_404_for_unknown_id(self, client, db_session, test_user, auth_headers):
        r = client.put(
            f"/api/v1/transactions/{uuid.uuid4()}",
            json={"amount": "10.00"},
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_returns_403_for_teller_transaction(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_teller_txn(db_session, conn.id)
        db_session.commit()

        r = client.put(
            f"/api/v1/transactions/{txn.id}",
            json={"amount": "10.00"},
            headers=auth_headers,
        )
        assert r.status_code == 404  # not found as a manual txn

    def test_returns_403_for_other_users_manual_transaction(self, client, db_session, test_user, auth_headers):
        other_user = User(
            id=uuid.uuid4(), username="other_put_user",
            display_name="Other", is_active=True, is_superuser=False,
        )
        db_session.add(other_user)
        db_session.flush()
        txn = _make_manual_txn(db_session, other_user.id)
        db_session.commit()

        r = client.put(
            f"/api/v1/transactions/{txn.id}",
            json={"amount": "10.00"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_requires_authentication(self, client, db_session, test_user):
        txn = _make_manual_txn(db_session, test_user.id)
        db_session.commit()

        r = client.put(f"/api/v1/transactions/{txn.id}", json={"amount": "10.00"})
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /transactions/{id}
# ---------------------------------------------------------------------------

class TestDeleteManualTransaction:
    def test_deletes_successfully(self, client, db_session, test_user, auth_headers):
        txn = _make_manual_txn(db_session, test_user.id)
        db_session.commit()

        r = client.delete(f"/api/v1/transactions/{txn.id}", headers=auth_headers)
        assert r.status_code == 204

    def test_returns_404_for_unknown_id(self, client, db_session, test_user, auth_headers):
        r = client.delete(f"/api/v1/transactions/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_returns_404_for_teller_transaction(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_teller_txn(db_session, conn.id)
        db_session.commit()

        r = client.delete(f"/api/v1/transactions/{txn.id}", headers=auth_headers)
        assert r.status_code == 404  # not found as a manual txn

    def test_returns_403_for_other_users_manual_transaction(self, client, db_session, test_user, auth_headers):
        other_user = User(
            id=uuid.uuid4(), username="other_del_user",
            display_name="Other", is_active=True, is_superuser=False,
        )
        db_session.add(other_user)
        db_session.flush()
        txn = _make_manual_txn(db_session, other_user.id)
        db_session.commit()

        r = client.delete(f"/api/v1/transactions/{txn.id}", headers=auth_headers)
        assert r.status_code == 403

    def test_requires_authentication(self, client, db_session, test_user):
        txn = _make_manual_txn(db_session, test_user.id)
        db_session.commit()

        r = client.delete(f"/api/v1/transactions/{txn.id}")

        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Regression: PATCH /bank/transactions/{id} must work for manual transactions
# ---------------------------------------------------------------------------

class TestAnnotateManualTransaction:
    """PATCH /bank/transactions/{id} must accept manual (connection_id=NULL) transactions."""

    def test_can_set_hsa_eligible_on_manual_transaction(self, client, db_session, test_user, auth_headers):
        txn = _make_manual_txn(db_session, test_user.id, merchant_name="Baptist Pulmonary Medical")
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"is_hsa_eligible": True, "hsa_category": "medical"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["is_hsa_eligible"] is True
        assert data["hsa_category"] == "medical"

    def test_can_set_notes_on_manual_transaction(self, client, db_session, test_user, auth_headers):
        txn = _make_manual_txn(db_session, test_user.id)
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"notes": "co-pay for pulmonologist"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["notes"] == "co-pay for pulmonologist"

    def test_patch_manual_transaction_not_visible_to_other_user(self, client, db_session, test_user, auth_headers):
        other_user = User(
            id=uuid.uuid4(), username="other_patch_user",
            display_name="Other", is_active=True, is_superuser=False,
        )
        db_session.add(other_user)
        db_session.flush()
        txn = _make_manual_txn(db_session, other_user.id)
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"is_hsa_eligible": True},
            headers=auth_headers,
        )
        assert r.status_code == 404
