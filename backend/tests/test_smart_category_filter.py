"""Tests for the adaptive Smart category filter.

Covers:
  - get_smart_hidden_categories() service function
  - GET  /bank/smart-filter/status
  - PUT  /bank/smart-filter/categories/{category}
  - DELETE /bank/smart-filter/categories/{category}
  - Smart filter integration in GET /bank/transactions
"""

import uuid
from datetime import date
from decimal import Decimal

from app.models.bank import BankConnection, BankTransaction, UserCategoryOverride
from app.services.rules_engine import (
    get_smart_hidden_categories,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_txn(db, connection_id, category=None, is_hsa_eligible=None, **kwargs):
    details = {"category": category} if category else None
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=connection_id,
        provider="teller",
        provider_transaction_id=f"txn_{uuid.uuid4().hex[:8]}",
        transaction_date=kwargs.get("transaction_date", date(2026, 3, 1)),
        description=kwargs.get("description", "Test Transaction"),
        amount=kwargs.get("amount", Decimal("-20.00")),
        status="posted",
        details=details,
        is_hsa_eligible=is_hsa_eligible,
    )
    db.add(txn)
    db.flush()
    return txn


# ---------------------------------------------------------------------------
# Service function tests
# ---------------------------------------------------------------------------


class TestGetSmartHiddenCategories:
    def test_default_hidden_contains_dining(self, db_session, test_user):
        """With no transaction history, SMART_DEFAULT_HIDDEN categories are hidden."""
        hidden = get_smart_hidden_categories(test_user.id, db_session)
        assert "dining" in hidden
        assert "entertainment" in hidden
        assert "fuel" in hidden

    def test_health_not_in_default_hidden(self, db_session, test_user):
        """health is never in the default hidden set."""
        hidden = get_smart_hidden_categories(test_user.id, db_session)
        assert "health" not in hidden

    def test_auto_promote_on_threshold(self, db_session, test_user):
        """Category with >= 10 reviewed, >= 15% HSA rate is promoted (not hidden)."""
        conn = _make_connection(db_session, test_user.id)
        # 10 reviewed, 2 HSA (20%)
        for _ in range(2):
            _make_txn(db_session, conn.id, category="shopping", is_hsa_eligible=True)
        for _ in range(8):
            _make_txn(db_session, conn.id, category="shopping", is_hsa_eligible=False)
        db_session.commit()

        hidden = get_smart_hidden_categories(test_user.id, db_session)
        assert "shopping" not in hidden

    def test_no_promote_below_count(self, db_session, test_user):
        """Only 9 reviewed — not enough to promote."""
        conn = _make_connection(db_session, test_user.id)
        for _ in range(2):
            _make_txn(db_session, conn.id, category="groceries", is_hsa_eligible=True)
        for _ in range(7):
            _make_txn(db_session, conn.id, category="groceries", is_hsa_eligible=False)
        db_session.commit()

        hidden = get_smart_hidden_categories(test_user.id, db_session)
        assert "groceries" in hidden

    def test_no_promote_below_rate(self, db_session, test_user):
        """10 reviewed but only 1 HSA (10%) — below the 15% threshold."""
        conn = _make_connection(db_session, test_user.id)
        for _ in range(1):
            _make_txn(db_session, conn.id, category="service", is_hsa_eligible=True)
        for _ in range(9):
            _make_txn(db_session, conn.id, category="service", is_hsa_eligible=False)
        db_session.commit()

        hidden = get_smart_hidden_categories(test_user.id, db_session)
        assert "service" in hidden

    def test_pin_show_overrides_default(self, db_session, test_user):
        """User pin_mode='show' removes category from hidden set."""
        db_session.add(UserCategoryOverride(
            user_id=test_user.id, category="dining", pin_mode="show"
        ))
        db_session.commit()

        hidden = get_smart_hidden_categories(test_user.id, db_session)
        assert "dining" not in hidden

    def test_pin_hide_overrides_promotion(self, db_session, test_user):
        """User pin_mode='hide' keeps category hidden even when auto-promoted."""
        conn = _make_connection(db_session, test_user.id)
        for _ in range(5):
            _make_txn(db_session, conn.id, category="shopping", is_hsa_eligible=True)
        for _ in range(5):
            _make_txn(db_session, conn.id, category="shopping", is_hsa_eligible=False)
        db_session.add(UserCategoryOverride(
            user_id=test_user.id, category="shopping", pin_mode="hide"
        ))
        db_session.commit()

        hidden = get_smart_hidden_categories(test_user.id, db_session)
        assert "shopping" in hidden

    def test_null_category_never_returned(self, db_session, test_user):
        """None/null is never included in the hidden set."""
        hidden = get_smart_hidden_categories(test_user.id, db_session)
        assert None not in hidden
        assert "" not in hidden


# ---------------------------------------------------------------------------
# Smart filter endpoint tests
# ---------------------------------------------------------------------------


class TestSmartFilterStatus:
    def test_returns_list(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn.id, category="dining")
        db_session.commit()

        r = client.get("/api/v1/bank/smart-filter/status", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        dining = next((d for d in data if d["category"] == "dining"), None)
        assert dining is not None
        assert dining["is_hidden_by_default"] is True
        assert dining["effective_smart_hidden"] is True

    def test_requires_auth(self, client):
        r = client.get("/api/v1/bank/smart-filter/status")
        assert r.status_code in (401, 403)


class TestSetCategoryOverride:
    def test_creates_pin(self, client, db_session, test_user, auth_headers):
        r = client.put(
            "/api/v1/bank/smart-filter/categories/dining",
            json={"pin_mode": "show"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["pin_mode"] == "show"

        row = db_session.query(UserCategoryOverride).filter_by(
            user_id=test_user.id, category="dining"
        ).first()
        assert row is not None
        assert row.pin_mode == "show"

    def test_updates_existing_pin(self, client, db_session, test_user, auth_headers):
        db_session.add(UserCategoryOverride(
            user_id=test_user.id, category="dining", pin_mode="show"
        ))
        db_session.commit()

        r = client.put(
            "/api/v1/bank/smart-filter/categories/dining",
            json={"pin_mode": "hide"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        row = db_session.query(UserCategoryOverride).filter_by(
            user_id=test_user.id, category="dining"
        ).first()
        assert row.pin_mode == "hide"

    def test_invalid_pin_mode(self, client, auth_headers):
        r = client.put(
            "/api/v1/bank/smart-filter/categories/dining",
            json={"pin_mode": "invalid"},
            headers=auth_headers,
        )
        assert r.status_code == 422


class TestDeleteCategoryOverride:
    def test_removes_pin(self, client, db_session, test_user, auth_headers):
        db_session.add(UserCategoryOverride(
            user_id=test_user.id, category="dining", pin_mode="show"
        ))
        db_session.commit()

        r = client.delete(
            "/api/v1/bank/smart-filter/categories/dining",
            headers=auth_headers,
        )
        assert r.status_code == 204
        row = db_session.query(UserCategoryOverride).filter_by(
            user_id=test_user.id, category="dining"
        ).first()
        assert row is None

    def test_idempotent(self, client, auth_headers):
        r = client.delete(
            "/api/v1/bank/smart-filter/categories/nonexistent",
            headers=auth_headers,
        )
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# Integration tests: smart filter applied in GET /bank/transactions
# ---------------------------------------------------------------------------


class TestSmartFilterIntegration:
    def test_smart_filter_hides_dining_by_default(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn.id, category="dining", description="NASHBIRD CHICKEN")
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        descriptions = [t["description"] for t in r.json()]
        assert "NASHBIRD CHICKEN" not in descriptions

    def test_reviewed_transaction_always_shows(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn.id, category="dining", description="FANCY RESTAURANT", is_hsa_eligible=False)
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        descriptions = [t["description"] for t in r.json()]
        assert "FANCY RESTAURANT" in descriptions

    def test_show_all_categories_bypasses_smart_filter(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn.id, category="dining", description="NASHBIRD CHICKEN")
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions",
            params={"show_all_categories": "true"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        descriptions = [t["description"] for t in r.json()]
        assert "NASHBIRD CHICKEN" in descriptions

    def test_specific_category_selection_bypasses_smart_filter(self, client, db_session, test_user, auth_headers):
        """Explicitly selecting a category shows all transactions in it, even smart-hidden ones."""
        conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn.id, category="dining", description="NASHBIRD CHICKEN")
        db_session.commit()

        r = client.get(
            "/api/v1/bank/transactions",
            params={"provider_category": "dining"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        descriptions = [t["description"] for t in r.json()]
        assert "NASHBIRD CHICKEN" in descriptions

    def test_pinned_show_bypasses_smart_filter(self, client, db_session, test_user, auth_headers):
        conn = _make_connection(db_session, test_user.id)
        _make_txn(db_session, conn.id, category="dining", description="NASHBIRD CHICKEN")
        db_session.add(UserCategoryOverride(
            user_id=test_user.id, category="dining", pin_mode="show"
        ))
        db_session.commit()

        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        descriptions = [t["description"] for t in r.json()]
        assert "NASHBIRD CHICKEN" in descriptions
