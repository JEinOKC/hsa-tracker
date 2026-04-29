"""Integration tests for portfolio endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.portfolio import HsaAccount, HsaHolding, HoldingSnapshot
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


# ---------------------------------------------------------------------------
# Holding snapshots
# ---------------------------------------------------------------------------

class TestHoldingSnapshots:
    def test_price_refresh_creates_snapshot(self, client, auth_headers, db_session, test_user):
        """Price refresh should write a HoldingSnapshot for each updated holding."""
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id, ticker="VTI", shares="10")

        with patch("app.api.v1.endpoints.portfolio.get_price_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.fetch_prices = AsyncMock(return_value={"VTI": Decimal("300.00")})
            mock_factory.return_value = mock_provider
            resp = client.post("/api/v1/portfolio/prices/refresh", headers=auth_headers)
            assert resp.status_code == 200

        snap = db_session.query(HoldingSnapshot).filter_by(holding_id=holding.id).first()
        assert snap is not None
        assert snap.ticker == "VTI"
        assert snap.shares == Decimal("10")
        assert snap.price == Decimal("300.00")
        assert snap.value == Decimal("3000.00")
        assert snap.user_id == test_user.id

    def test_price_refresh_upserts_same_day(self, client, auth_headers, db_session, test_user):
        """Two refreshes on the same day should produce only one snapshot row."""
        account = _make_account(db_session, test_user.id)
        _make_holding(db_session, account.id, ticker="VTI", shares="10")

        def _refresh(price):
            with patch("app.api.v1.endpoints.portfolio.get_price_provider") as mock_factory:
                mock_provider = AsyncMock()
                mock_provider.fetch_prices = AsyncMock(return_value={"VTI": Decimal(str(price))})
                mock_factory.return_value = mock_provider
                client.post("/api/v1/portfolio/prices/refresh", headers=auth_headers)

        _refresh("250.00")
        _refresh("260.00")  # second refresh same day — should update, not insert

        count = db_session.query(HoldingSnapshot).count()
        assert count == 1
        snap = db_session.query(HoldingSnapshot).first()
        assert snap.price == Decimal("260.00")  # latest price wins

    def test_snapshot_captures_updated_share_count(self, client, auth_headers, db_session, test_user):
        """Updating shares on a holding with a known price should update today's snapshot."""
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id, ticker="FSKAX", shares="20")
        holding.last_known_price = Decimal("100.00")
        db_session.commit()

        resp = client.patch(
            f"/api/v1/portfolio/accounts/{account.id}/holdings/{holding.id}",
            json={"shares": "25.5"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        snap = db_session.query(HoldingSnapshot).filter_by(holding_id=holding.id).first()
        assert snap is not None
        assert snap.shares == Decimal("25.5")
        assert snap.value == Decimal("2550.00")  # 25.5 * 100

    def test_snapshot_skipped_when_no_price(self, client, auth_headers, db_session, test_user):
        """Updating shares when last_known_price is None should not create a snapshot."""
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id, ticker="FSKAX", shares="5")
        # No price set

        client.patch(
            f"/api/v1/portfolio/accounts/{account.id}/holdings/{holding.id}",
            json={"shares": "10"},
            headers=auth_headers,
        )

        assert db_session.query(HoldingSnapshot).count() == 0

    def test_history_requires_auth(self, client):
        assert client.get("/api/v1/portfolio/history").status_code == 403

    def test_history_returns_daily_totals(self, client, auth_headers, db_session, test_user):
        """History endpoint should aggregate snapshots by date."""
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id, ticker="VTI", shares="10")

        # Manually insert two snapshots on different days
        day1 = datetime(2026, 4, 1, 12, 0, 0)
        day2 = datetime(2026, 4, 2, 12, 0, 0)
        for snap_at, price, shares in [(day1, Decimal("250.00"), Decimal("10")), (day2, Decimal("255.00"), Decimal("12"))]:
            db_session.add(HoldingSnapshot(
                id=uuid.uuid4(),
                holding_id=holding.id,
                account_id=account.id,
                user_id=test_user.id,
                ticker="VTI",
                shares=shares,
                price=price,
                value=(shares * price).quantize(Decimal("0.01")),
                snapshotted_at=snap_at,
            ))
        db_session.commit()

        resp = client.get("/api/v1/portfolio/history?days=365", headers=auth_headers)
        assert resp.status_code == 200
        points = resp.json()["points"]
        assert len(points) == 2
        assert points[0]["date"] == "2026-04-01"
        assert float(points[0]["total_value"]) == pytest.approx(2500.00)
        assert points[1]["date"] == "2026-04-02"
        assert float(points[1]["total_value"]) == pytest.approx(3060.00)

    def test_history_excludes_other_user_snapshots(self, client, auth_headers, db_session, test_user):
        """Snapshots belonging to other users must not appear in the history."""
        other_user = _make_user(db_session, username="otherusersnap")
        other_account = _make_account(db_session, other_user.id)
        other_holding = _make_holding(db_session, other_account.id, ticker="SPY")
        db_session.add(HoldingSnapshot(
            id=uuid.uuid4(),
            holding_id=other_holding.id,
            account_id=other_account.id,
            user_id=other_user.id,
            ticker="SPY",
            shares=Decimal("5"),
            price=Decimal("500.00"),
            value=Decimal("2500.00"),
            snapshotted_at=datetime.utcnow(),
        ))
        db_session.commit()

        resp = client.get("/api/v1/portfolio/history?days=365", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["points"] == []
