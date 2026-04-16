"""Tests for coverage window warnings and strict eligibility calculations.

Covers:
  - eligibility_warning field on transaction list and annotate responses
  - strict dashboard filter (hsa_spending excludes out-of-window transactions)
  - PATCH /households/mine strict_eligibility toggle
  - GET /households/mine is_admin field
"""

import uuid
from datetime import date, datetime

import pytest

from app.models.bank import BankConnection, BankTransaction
from app.models.family import FamilyMember, HsaEligibilityPeriod
from app.models.household import Household, HouseholdMembership, HouseholdRole


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_connection(db, user_id):
    conn = BankConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="teller",
        provider_account_id="acct_test",
        account_name="HSA Checking",
        account_type="depository",
        account_subtype="hsa",
        institution_name="Test Bank",
        last_four="9999",
        currency="USD",
        enrollment_token="tok_test",
        is_active=True,
    )
    db.add(conn)
    db.flush()
    return conn


def _make_transaction(db, connection_id, amount="-50.00", txn_date=None, is_hsa=True, member_id=None):
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=connection_id,
        provider="teller",
        provider_transaction_id=f"ptxn_{uuid.uuid4().hex[:8]}",
        transaction_date=txn_date or date(2026, 3, 15),
        description="Test Transaction",
        amount=amount,
        status="posted",
        is_hsa_eligible=is_hsa,
        family_member_id=member_id,
        created_at=datetime.utcnow(),
    )
    db.add(txn)
    db.flush()
    return txn


def _make_member(db, household_id, name="Alice"):
    m = FamilyMember(
        id=uuid.uuid4(),
        household_id=household_id,
        name=name,
        member_relationship="self",
        is_tax_dependent=False,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(m)
    db.flush()
    return m


def _make_period(db, member_id, start, end=None):
    p = HsaEligibilityPeriod(
        id=uuid.uuid4(),
        family_member_id=member_id,
        start_date=start,
        end_date=end,
        created_at=datetime.utcnow(),
    )
    db.add(p)
    db.flush()
    return p


# ── eligibility_warning on GET /bank/transactions ──────────────────────────────

class TestEligibilityWarningOnList:
    def test_no_member_assigned_returns_warning(self, client, auth_headers, db_session, test_user, test_user_household):
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id, member_id=None)
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()[0]["eligibility_warning"] is True

    def test_member_with_no_periods_returns_warning(self, client, auth_headers, db_session, test_user, test_user_household):
        conn = _make_connection(db_session, test_user.id)
        member = _make_member(db_session, test_user_household.id)
        _make_transaction(db_session, conn.id, member_id=member.id)
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()[0]["eligibility_warning"] is True

    def test_member_outside_period_returns_warning(self, client, auth_headers, db_session, test_user, test_user_household):
        conn = _make_connection(db_session, test_user.id)
        member = _make_member(db_session, test_user_household.id)
        # Period ends before the transaction date
        _make_period(db_session, member.id, start=date(2025, 1, 1), end=date(2025, 12, 31))
        _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 15), member_id=member.id)
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()[0]["eligibility_warning"] is True

    def test_member_inside_period_no_warning(self, client, auth_headers, db_session, test_user, test_user_household):
        conn = _make_connection(db_session, test_user.id)
        member = _make_member(db_session, test_user_household.id)
        # Open-ended period starting before the transaction
        _make_period(db_session, member.id, start=date(2026, 1, 1), end=None)
        _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 15), member_id=member.id)
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()[0]["eligibility_warning"] is False

    def test_member_inside_closed_period_no_warning(self, client, auth_headers, db_session, test_user, test_user_household):
        conn = _make_connection(db_session, test_user.id)
        member = _make_member(db_session, test_user_household.id)
        _make_period(db_session, member.id, start=date(2026, 1, 1), end=date(2026, 12, 31))
        _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 15), member_id=member.id)
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()[0]["eligibility_warning"] is False

    def test_no_household_all_transactions_warned(self, client, auth_headers, db_session, test_user):
        # test_user has no household — unassigned transactions should be warned
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id, member_id=None)
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()[0]["eligibility_warning"] is True


# ── eligibility_warning on PATCH /bank/transactions/{id} ──────────────────────

class TestEligibilityWarningOnAnnotate:
    def test_annotate_returns_warning_when_outside_period(self, client, auth_headers, db_session, test_user, test_user_household):
        conn = _make_connection(db_session, test_user.id)
        member = _make_member(db_session, test_user_household.id)
        _make_period(db_session, member.id, start=date(2025, 1, 1), end=date(2025, 12, 31))
        txn = _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 15))
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"family_member_id": str(member.id)},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["eligibility_warning"] is True

    def test_annotate_returns_no_warning_when_inside_period(self, client, auth_headers, db_session, test_user, test_user_household):
        conn = _make_connection(db_session, test_user.id)
        member = _make_member(db_session, test_user_household.id)
        _make_period(db_session, member.id, start=date(2026, 1, 1), end=None)
        txn = _make_transaction(db_session, conn.id, txn_date=date(2026, 3, 15))
        db_session.commit()

        r = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"family_member_id": str(member.id)},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["eligibility_warning"] is False


# ── strict eligibility in dashboard summary ────────────────────────────────────

class TestStrictDashboard:
    def _setup(self, db, test_user, test_user_household):
        conn = _make_connection(db, test_user.id)
        member = _make_member(db, test_user_household.id)
        return conn, member

    def test_strict_excludes_unassigned_transactions(self, client, auth_headers, db_session, test_user, test_user_household):
        test_user_household.strict_eligibility = True
        conn, _ = self._setup(db_session, test_user, test_user_household)
        _make_transaction(db_session, conn.id, amount="-100.00", member_id=None)
        db_session.commit()

        r = client.get("/api/v1/bank/summary", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["hsa_spending"] == 0.0

    def test_strict_excludes_out_of_window_transactions(self, client, auth_headers, db_session, test_user, test_user_household):
        test_user_household.strict_eligibility = True
        conn, member = self._setup(db_session, test_user, test_user_household)
        _make_period(db_session, member.id, start=date(2025, 1, 1), end=date(2025, 12, 31))
        _make_transaction(db_session, conn.id, amount="-75.00", txn_date=date(2026, 3, 15), member_id=member.id)
        db_session.commit()

        r = client.get("/api/v1/bank/summary", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["hsa_spending"] == 0.0

    def test_strict_includes_in_window_transactions(self, client, auth_headers, db_session, test_user, test_user_household):
        test_user_household.strict_eligibility = True
        conn, member = self._setup(db_session, test_user, test_user_household)
        _make_period(db_session, member.id, start=date(2026, 1, 1), end=None)
        _make_transaction(db_session, conn.id, amount="-75.00", txn_date=date(2026, 3, 15), member_id=member.id)
        db_session.commit()

        r = client.get("/api/v1/bank/summary", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["hsa_spending"] == pytest.approx(-75.0)

    def test_relaxed_includes_all_hsa_transactions(self, client, auth_headers, db_session, test_user, test_user_household):
        test_user_household.strict_eligibility = False
        conn, member = self._setup(db_session, test_user, test_user_household)
        # No eligibility periods — but strict is off, so it still counts
        _make_transaction(db_session, conn.id, amount="-50.00", member_id=member.id)
        db_session.commit()

        r = client.get("/api/v1/bank/summary", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["hsa_spending"] == pytest.approx(-50.0)

    def test_eligible_amount_overrides_full_amount_in_summary(self, client, auth_headers, db_session, test_user, test_user_household):
        """When eligible_amount is set, only the partial amount counts toward hsa_spending."""
        test_user_household.strict_eligibility = False
        conn, _ = self._setup(db_session, test_user, test_user_household)
        from decimal import Decimal
        _make_transaction(db_session, conn.id, amount="-100.00")
        # Second txn with partial eligible amount (stored with same sign as amount)
        txn = _make_transaction(db_session, conn.id, amount="-80.00")
        txn.eligible_amount = Decimal("-20.00")
        db_session.commit()

        r = client.get("/api/v1/bank/summary", headers=auth_headers)
        assert r.status_code == 200
        # Full -100 + eligible -20 = -120 (not -180)
        assert r.json()["hsa_spending"] == pytest.approx(-120.0)


# ── PATCH /households/mine ──────────────────────────────────────────────────────

class TestHouseholdSettings:
    def test_admin_can_toggle_strict_eligibility(self, client, auth_headers, db_session, test_user, test_user_household):
        assert test_user_household.strict_eligibility is True  # default

        r = client.patch("/api/v1/households/mine", json={"strict_eligibility": False}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["household"]["strict_eligibility"] is False

        r2 = client.patch("/api/v1/households/mine", json={"strict_eligibility": True}, headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["household"]["strict_eligibility"] is True

    def test_non_admin_gets_403(self, client, db_session, test_user, test_user_household):
        from app.utils.security import create_access_token

        # Create a second user who is NOT admin
        other = FamilyMember.__new__(FamilyMember)  # not needed — just need a User
        from app.models.user import User
        other_user = User(
            id=uuid.uuid4(),
            username="nonAdmin",
            display_name="Non Admin",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(other_user)
        db_session.flush()

        role = db_session.query(HouseholdRole).filter_by(household_id=test_user_household.id).first()
        membership = HouseholdMembership(
            id=uuid.uuid4(),
            household_id=test_user_household.id,
            user_id=other_user.id,
            role_id=role.id,
            is_admin=False,
            joined_at=datetime.utcnow(),
        )
        db_session.add(membership)
        db_session.commit()

        token = create_access_token({"sub": str(other_user.id)})
        other_headers = {"Authorization": f"Bearer {token}"}

        r = client.patch("/api/v1/households/mine", json={"strict_eligibility": False}, headers=other_headers)
        assert r.status_code == 403

    def test_get_mine_includes_is_admin_true(self, client, auth_headers, test_user_household):
        r = client.get("/api/v1/households/mine", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["is_admin"] is True

    def test_get_mine_includes_strict_eligibility(self, client, auth_headers, test_user_household):
        r = client.get("/api/v1/households/mine", headers=auth_headers)
        assert r.status_code == 200
        assert "strict_eligibility" in r.json()["household"]
