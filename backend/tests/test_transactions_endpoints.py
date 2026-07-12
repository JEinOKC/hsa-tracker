"""Tests for the cross-account transaction endpoints.

  GET   /bank/transactions        - list all transactions for the current user
  PATCH /bank/transactions/{id}   - annotate a transaction with HSA metadata
"""

import uuid
from datetime import date
from decimal import Decimal

from app.models.bank import BankConnection, BankTransaction
from app.models.user import User


def _make_connection(db, user_id):
    conn = BankConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="teller",
        provider_account_id=f"acct_{uuid.uuid4().hex[:8]}",
        account_name="HSA Checking",
        institution_name="First Bank",
        currency="USD",
        is_active=True,
    )
    db.add(conn)
    db.flush()
    return conn


def _make_txn(db, connection_id, **kwargs):
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=connection_id,
        provider="teller",
        provider_transaction_id=f"txn_{uuid.uuid4().hex[:8]}",
        transaction_date=kwargs.get("transaction_date", date(2026, 3, 1)),
        description=kwargs.get("description", "CVS Pharmacy"),
        amount=kwargs.get("amount", Decimal("-42.00")),
        status=kwargs.get("status", "posted"),
    )
    db.add(txn)
    db.flush()
    return txn


class TestListAllTransactions:
    def test_returns_transactions_across_all_accounts(self, client, db_session, test_user, auth_headers):
        conn1 = _make_connection(db_session, test_user.id)
        conn2 = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn1.id, description="CVS Pharmacy")
        _make_txn(db_session, conn2.id, description="Walgreens")
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        descriptions = [t["description"] for t in r.json()]
        assert "CVS Pharmacy" in descriptions
        assert "Walgreens" in descriptions

    def test_does_not_return_other_users_transactions(self, client, db_session, test_user, auth_headers):
        other_user = User(id=uuid.uuid4(), username="other_txn_user", display_name="Other", is_active=True, is_superuser=False)
        db_session.add(other_user)
        db_session.flush()
        other_conn = BankConnection(
            id=uuid.uuid4(),
            user_id=other_user.id,
            provider="teller",
            provider_account_id="other_acct",
            account_name="Other Bank",
            currency="USD",
            is_active=True,
        )
        db_session.add(other_conn)
        db_session.flush()
        _make_txn(db_session, other_conn.id, description="Other User Txn")
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        assert all(t["description"] != "Other User Txn" for t in r.json())

    def test_filter_hsa_eligible_true(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        t1 = _make_txn(db_session, conn.id, description="Doctor Visit")
        t2 = _make_txn(db_session, conn.id, description="Spotify")
        t1.is_hsa_eligible = True
        t2.is_hsa_eligible = False
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", params={"is_hsa_eligible": True}, headers=auth_headers)
        assert r.status_code == 200
        assert all(t["is_hsa_eligible"] is True for t in r.json())

    def test_filter_by_family_member(self, client, db_session, test_user, auth_headers, test_user_household):
        from app.models.family import FamilyMember
        conn = _make_connection(db_session, test_user.id)
        member = FamilyMember(
            id=uuid.uuid4(),
            household_id=test_user_household.id,
            name="Jane",
            member_relationship="spouse",
        )
        db_session.add(member)
        db_session.flush()

        t1 = _make_txn(db_session, conn.id, description="Jane's Doctor")
        _t2 = _make_txn(db_session, conn.id, description="Other")
        t1.family_member_id = member.id
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions",
            params={"family_member_id": str(member.id)},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["description"] == "Jane's Doctor"

    def test_requires_authentication(self, client):
        r = client.get("/api/v1/bank/transactions")
        assert r.status_code == 401


class TestAnnotateTransaction:
    def test_mark_hsa_eligible(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id)
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"is_hsa_eligible": True},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["is_hsa_eligible"] is True

    def test_assign_family_member(self, client, db_session, test_user, auth_headers, test_user_household):
        from app.models.family import FamilyMember
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id)
        member = FamilyMember(
            id=uuid.uuid4(),
            household_id=test_user_household.id,
            name="Bob",
            member_relationship="other",
        )
        db_session.add(member)
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"family_member_id": str(member.id)},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["family_member_id"] == str(member.id)

    def test_set_hsa_category_and_notes(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id)
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"hsa_category": "dental", "notes": "Annual checkup"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["hsa_category"] == "dental"
        assert data["notes"] == "Annual checkup"

    def test_only_provided_fields_are_updated(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id)
        txn.is_hsa_eligible = True
        txn.notes = "existing note"
        db_session.commit()

        # Only update hsa_category — is_hsa_eligible and notes should be unchanged
        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"hsa_category": "vision"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["is_hsa_eligible"] is True
        assert data["notes"] == "existing note"
        assert data["hsa_category"] == "vision"

    def test_cannot_annotate_other_users_transaction(self, client, db_session, test_user, auth_headers):
        other_user = User(id=uuid.uuid4(), username="other_annotate_user", display_name="Other2", is_active=True, is_superuser=False)
        db_session.add(other_user)
        db_session.flush()
        other_conn = BankConnection(
            id=uuid.uuid4(),
            user_id=other_user.id,
            provider="teller",
            provider_account_id="other",
            account_name="Other",
            currency="USD",
            is_active=True,
        )
        db_session.add(other_conn)
        db_session.flush()
        other_txn = _make_txn(db_session, other_conn.id)
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{other_txn.id}",
            json={"is_hsa_eligible": True},
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_returns_404_for_unknown_transaction(self, client, auth_headers):
        r = client.patch(
            f"/api/v1/bank/transactions/{uuid.uuid4()}",
            json={"is_hsa_eligible": True},
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_set_eligible_amount(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id, amount=Decimal("-100.00"), is_hsa_eligible=True)
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"eligible_amount": "20.00"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["eligible_amount"] == "20.00"

    def test_clear_eligible_amount(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id, amount=Decimal("-100.00"), eligible_amount=Decimal("20.00"))
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"eligible_amount": None},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["eligible_amount"] is None


class TestCountTransactions:
    def test_count_returns_total(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn.id, description="CVS")
        _make_txn(db_session, conn.id, description="Walgreens")
        _make_txn(db_session, conn.id, description="Target")
        db_session.commit()

        r = client.get("/api/v1/bank/transactions/count", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == 3

    def test_count_filters_by_teller_category(self, client, db_session, test_user, auth_headers):
        """Regression: category filter applies to count, old txns without category are excluded."""
        conn = _make_connection(db_session, test_user.id)
        t1 = _make_txn(db_session, conn.id, description="Doctor")
        t2 = _make_txn(db_session, conn.id, description="Dentist")
        t3 = _make_txn(db_session, conn.id, description="Grocery")
        t1.details = {"category": "health"}
        t2.details = {"category": "health"}
        t3.details = {"category": "food_and_drink"}
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions/count",
            params={"teller_category": "health"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json() == 2

    def test_count_excludes_txns_without_category_field(self, client, db_session, test_user, auth_headers):
        """Old transactions without details.category are excluded when category filter is active."""
        conn = _make_connection(db_session, test_user.id)
        t1 = _make_txn(db_session, conn.id, description="Modern Health Txn")
        t2 = _make_txn(db_session, conn.id, description="Old Health Txn")
        t1.details = {"category": "health"}
        t2.details = {}  # no category key
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions/count",
            params={"teller_category": "health"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json() == 1

    def test_count_returns_zero_when_no_matches(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn.id, description="Grocery")
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions/count",
            params={"teller_category": "health"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json() == 0

    def test_count_requires_auth(self, client):
        r = client.get("/api/v1/bank/transactions/count")
        assert r.status_code == 401

    def test_count_isolates_by_user(self, client, db_session, test_user, auth_headers):
        other_user = User(
            id=uuid.uuid4(), username="count_other", display_name="Other",
            is_active=True, is_superuser=False,
        )
        db_session.add(other_user)
        db_session.flush()
        other_conn = _make_connection(db_session, other_user.id)
        _make_txn(db_session, other_conn.id, description="Other txn")
        my_conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, my_conn.id, description="My txn")
        db_session.commit()

        r = client.get("/api/v1/bank/transactions/count", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == 1


class TestIncludePotentialHsa:
    def test_hsa_tab_excludes_potential_by_default(self, client, db_session, test_user, auth_headers):
        """Regression: potential_hsa txns are invisible on HSA tab without the flag."""
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id, description="Dentist 2025")
        txn.auto_flag = "potential_hsa"
        txn.is_hsa_eligible = None
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions",
            params={"is_hsa_eligible": True},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert all(t["description"] != "Dentist 2025" for t in r.json())

    def test_hsa_tab_includes_potential_when_flag_set(self, client, db_session, test_user, auth_headers):
        """Regression: potential_hsa txns appear when include_potential_hsa=true."""
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id, description="Dentist 2025")
        txn.auto_flag = "potential_hsa"
        txn.is_hsa_eligible = None
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions",
            params={"is_hsa_eligible": True, "include_potential_hsa": True},
            headers=auth_headers,
        )
        assert r.status_code == 200
        descriptions = [t["description"] for t in r.json()]
        assert "Dentist 2025" in descriptions

    def test_non_hsa_not_included_with_potential_flag(self, client, db_session, test_user, auth_headers):
        """Unreviewed txns with no auto_flag are NOT included even with include_potential_hsa=true."""
        conn = _make_connection(db_session, test_user.id)
        txn = _make_txn(db_session, conn.id, description="Random Purchase")
        txn.auto_flag = None
        txn.is_hsa_eligible = None
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions",
            params={"is_hsa_eligible": True, "include_potential_hsa": True},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert all(t["description"] != "Random Purchase" for t in r.json())

    def test_count_endpoint_respects_include_potential_hsa(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        confirmed = _make_txn(db_session, conn.id, description="Confirmed HSA")
        confirmed.is_hsa_eligible = True
        potential = _make_txn(db_session, conn.id, description="Potential HSA")
        potential.auto_flag = "potential_hsa"
        potential.is_hsa_eligible = None
        db_session.commit()

        r_default = client.get(
            "/api/v1/bank/transactions/count",
            params={"is_hsa_eligible": True},
            headers=auth_headers,
        )
        assert r_default.json() == 1

        r_with_potential = client.get(
            "/api/v1/bank/transactions/count",
            params={"is_hsa_eligible": True, "include_potential_hsa": True},
            headers=auth_headers,
        )
        assert r_with_potential.json() == 2
