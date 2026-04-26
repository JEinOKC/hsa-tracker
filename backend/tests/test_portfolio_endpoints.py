"""Integration tests for portfolio endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.portfolio import HsaAccount, HsaHolding
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db_session, username="otheruser"):
    """Create a minimal user with no credentials (sufficient for FK references)."""
    user = User(
        id=uuid.uuid4(),
        username=username,
        display_name=username.capitalize(),
        email=None,
        hashed_password=None,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_account(db_session, user_id, institution_name="Fidelity", **kwargs):
    account = HsaAccount(
        id=uuid.uuid4(),
        user_id=user_id,
        institution_name=institution_name,
        nickname=kwargs.get("nickname"),
        account_type=kwargs.get("account_type", "both"),
        is_active=kwargs.get("is_active", True),
        cash_balance=kwargs.get("cash_balance"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def _make_holding(db_session, account_id, ticker="VTI", shares="10.0"):
    holding = HsaHolding(
        id=uuid.uuid4(),
        account_id=account_id,
        ticker=ticker,
        shares=Decimal(shares),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(holding)
    db_session.commit()
    db_session.refresh(holding)
    return holding


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestPortfolioAuthRequired:
    def test_list_accounts_requires_auth(self, client):
        assert client.get("/api/v1/portfolio/accounts").status_code == 403

    def test_create_account_requires_auth(self, client):
        assert client.post("/api/v1/portfolio/accounts", json={"institution_name": "Fidelity"}).status_code == 403

    def test_summary_requires_auth(self, client):
        assert client.get("/api/v1/portfolio/summary").status_code == 403

    def test_projection_requires_auth(self, client):
        assert client.get("/api/v1/portfolio/projection").status_code == 403

    def test_refresh_prices_requires_auth(self, client):
        assert client.post("/api/v1/portfolio/prices/refresh").status_code == 403


# ---------------------------------------------------------------------------
# Account CRUD
# ---------------------------------------------------------------------------

class TestCreateAccount:
    def test_create_account_happy_path(self, client, auth_headers):
        resp = client.post(
            "/api/v1/portfolio/accounts",
            json={"institution_name": "Fidelity", "account_type": "investment"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["institution_name"] == "Fidelity"
        assert data["account_type"] == "investment"
        assert data["holdings"] == []

    def test_create_account_requires_institution_name(self, client, auth_headers):
        resp = client.post(
            "/api/v1/portfolio/accounts",
            json={"account_type": "investment"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_account_with_cash_balance(self, client, auth_headers):
        resp = client.post(
            "/api/v1/portfolio/accounts",
            json={"institution_name": "Rippling", "cash_balance": "1500.00"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["cash_balance"] == "1500.00"


class TestListAccounts:
    def test_returns_only_user_accounts(self, client, auth_headers, db_session, test_user):
        _make_account(db_session, test_user.id, institution_name="My Fidelity")
        # Account owned by a different user — should not appear
        other_user = _make_user(db_session)
        _make_account(db_session, other_user.id, institution_name="Other User HSA")

        resp = client.get("/api/v1/portfolio/accounts", headers=auth_headers)
        assert resp.status_code == 200
        names = [a["institution_name"] for a in resp.json()]
        assert "My Fidelity" in names
        assert "Other User HSA" not in names

    def test_excludes_inactive_accounts(self, client, auth_headers, db_session, test_user):
        _make_account(db_session, test_user.id, institution_name="Active HSA")
        _make_account(db_session, test_user.id, institution_name="Old HSA", is_active=False)

        resp = client.get("/api/v1/portfolio/accounts", headers=auth_headers)
        names = [a["institution_name"] for a in resp.json()]
        assert "Active HSA" in names
        assert "Old HSA" not in names


class TestUpdateAccount:
    def test_update_institution_name(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        resp = client.patch(
            f"/api/v1/portfolio/accounts/{account.id}",
            json={"institution_name": "Updated Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["institution_name"] == "Updated Name"

    def test_update_returns_403_for_other_user(self, client, auth_headers, db_session):
        other_user = _make_user(db_session, username="otheruserupdate")
        account = _make_account(db_session, other_user.id)
        resp = client.patch(
            f"/api/v1/portfolio/accounts/{account.id}",
            json={"institution_name": "Hijacked"},
            headers=auth_headers,
        )
        assert resp.status_code == 404  # not visible to this user at all


class TestDeleteAccount:
    def test_delete_account_and_cascades_holdings(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id)

        resp = client.delete(f"/api/v1/portfolio/accounts/{account.id}", headers=auth_headers)
        assert resp.status_code == 204

        # Holding should be gone too
        assert db_session.query(HsaHolding).filter_by(id=holding.id).first() is None

    def test_delete_returns_404_for_missing_account(self, client, auth_headers):
        resp = client.delete(f"/api/v1/portfolio/accounts/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Holdings CRUD
# ---------------------------------------------------------------------------

class TestHoldings:
    def test_add_holding(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        resp = client.post(
            f"/api/v1/portfolio/accounts/{account.id}/holdings",
            json={"ticker": "vti", "shares": "10.5"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ticker"] == "VTI"  # should be uppercased
        assert data["shares"] == "10.500000"

    def test_delete_holding(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id)

        resp = client.delete(
            f"/api/v1/portfolio/accounts/{account.id}/holdings/{holding.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204
        assert db_session.query(HsaHolding).filter_by(id=holding.id).first() is None

    def test_add_holding_404_for_other_user_account(self, client, auth_headers, db_session):
        other_user = _make_user(db_session, username="otheruserholding")
        account = _make_account(db_session, other_user.id)
        resp = client.post(
            f"/api/v1/portfolio/accounts/{account.id}/holdings",
            json={"ticker": "VTI", "shares": "5"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Price refresh
# ---------------------------------------------------------------------------

class TestPriceRefresh:
    def test_refresh_updates_last_known_price(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id, ticker="VTI", shares="10")
        assert holding.last_known_price is None

        with patch(
            "app.api.v1.endpoints.portfolio.get_price_provider"
        ) as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.fetch_prices = AsyncMock(return_value={"VTI": Decimal("250.00")})
            mock_factory.return_value = mock_provider

            resp = client.post("/api/v1/portfolio/prices/refresh", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["updated"] == 1

        db_session.refresh(holding)
        assert holding.last_known_price == Decimal("250.00")
        assert holding.last_price_fetched_at is not None

    def test_refresh_returns_zero_when_no_holdings(self, client, auth_headers):
        with patch("app.api.v1.endpoints.portfolio.get_price_provider"):
            resp = client.post("/api/v1/portfolio/prices/refresh", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestPortfolioSummary:
    def test_summary_correct_arithmetic(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id, cash_balance=Decimal("500.00"))
        holding = _make_holding(db_session, account.id, ticker="VTI", shares="10")
        # Manually set price
        holding.last_known_price = Decimal("200.00")
        db_session.commit()

        resp = client.get("/api/v1/portfolio/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        accounts = data["accounts"]
        assert len(accounts) == 1
        # invested = 10 * 200 = 2000, total = 500 + 2000 = 2500
        assert float(accounts[0]["invested_value"]) == pytest.approx(2000.00)
        assert float(accounts[0]["total_value"]) == pytest.approx(2500.00)
        assert float(data["total_value"]) == pytest.approx(2500.00)

    def test_summary_empty_when_no_accounts(self, client, auth_headers):
        resp = client.get("/api/v1/portfolio/summary", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["accounts"] == []


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

class TestProjection:
    def test_projection_year_zero_equals_starting_value(self, client, auth_headers, db_session, test_user):
        _make_account(db_session, test_user.id, cash_balance=Decimal("1000.00"))

        resp = client.get("/api/v1/portfolio/projection?years=5&annual_return=7", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        points = data["points"]
        assert points[0]["year"] == 0
        assert float(points[0]["value"]) == pytest.approx(float(data["starting_value"]))

    def test_projection_year_1_at_10_percent(self, client, auth_headers, db_session, test_user):
        _make_account(db_session, test_user.id, cash_balance=Decimal("1000.00"))

        resp = client.get("/api/v1/portfolio/projection?years=1&annual_return=10", headers=auth_headers)
        assert resp.status_code == 200
        points = resp.json()["points"]
        year_1 = next(p for p in points if p["year"] == 1)
        assert float(year_1["value"]) == pytest.approx(1100.00, abs=0.02)

    def test_projection_empty_portfolio_starts_at_zero(self, client, auth_headers):
        resp = client.get("/api/v1/portfolio/projection?years=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["starting_value"]) == 0.0
        # All values should stay at 0
        for p in data["points"]:
            assert float(p["value"]) == pytest.approx(0.0)
