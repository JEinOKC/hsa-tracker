"""Integration tests for portfolio endpoints."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from app.models.portfolio import (
    AutoInvestAllocation,
    AutoInvestSchedule,
    HoldingSnapshot,
    HsaAccount,
    HsaHolding,
)
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
        assert client.get("/api/v1/portfolio/accounts").status_code == 401

    def test_create_account_requires_auth(self, client):
        assert client.post("/api/v1/portfolio/accounts", json={"institution_name": "Fidelity"}).status_code == 401

    def test_summary_requires_auth(self, client):
        assert client.get("/api/v1/portfolio/summary").status_code == 401

    def test_projection_requires_auth(self, client):
        assert client.get("/api/v1/portfolio/projection").status_code == 401

    def test_refresh_prices_requires_auth(self, client):
        assert client.post("/api/v1/portfolio/prices/refresh").status_code == 401


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
        assert client.get("/api/v1/portfolio/history").status_code == 401

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


# ---------------------------------------------------------------------------
# Auto-Invest Schedules
# ---------------------------------------------------------------------------

def _make_schedule(db_session, account_id, user_id, contribution_amount="150.00",
                   frequency="biweekly", days_until_due=14):
    next_date = date.today() + timedelta(days=days_until_due)
    schedule = AutoInvestSchedule(
        id=uuid.uuid4(),
        account_id=account_id,
        user_id=user_id,
        contribution_amount=Decimal(contribution_amount),
        frequency=frequency,
        next_contribution_date=next_date,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(schedule)
    db_session.commit()
    db_session.refresh(schedule)
    return schedule


def _make_allocation(db_session, schedule_id, holding_id, ticker, percentage):
    alloc = AutoInvestAllocation(
        id=uuid.uuid4(),
        schedule_id=schedule_id,
        holding_id=holding_id,
        ticker=ticker,
        percentage=Decimal(str(percentage)),
    )
    db_session.add(alloc)
    db_session.commit()
    return alloc


class TestAutoInvestScheduleAuth:
    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/portfolio/accounts/fake-id/auto-invest").status_code == 401

    def test_create_requires_auth(self, client):
        assert client.post("/api/v1/portfolio/accounts/fake-id/auto-invest", json={}).status_code == 401

    def test_apply_requires_auth(self, client):
        assert client.post("/api/v1/portfolio/auto-invest/fake-id/apply").status_code == 401


class TestAutoInvestScheduleCRUD:
    def test_create_schedule_happy_path(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        h1 = _make_holding(db_session, account.id, ticker="VTI", shares="10")
        h2 = _make_holding(db_session, account.id, ticker="FZROX", shares="5")

        next_date = (date.today() + timedelta(days=14)).isoformat()
        resp = client.post(
            f"/api/v1/portfolio/accounts/{account.id}/auto-invest",
            json={
                "contribution_amount": "150.00",
                "frequency": "biweekly",
                "next_contribution_date": next_date,
                "allocations": [
                    {"holding_id": str(h1.id), "ticker": "VTI", "percentage": "90.00"},
                    {"holding_id": str(h2.id), "ticker": "FZROX", "percentage": "10.00"},
                ],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["contribution_amount"] == "150.00"
        assert data["frequency"] == "biweekly"
        assert len(data["allocations"]) == 2
        assert data["is_active"] is True

    def test_create_requires_allocations_sum_to_100(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        h1 = _make_holding(db_session, account.id, ticker="VTI", shares="10")

        next_date = (date.today() + timedelta(days=14)).isoformat()
        resp = client.post(
            f"/api/v1/portfolio/accounts/{account.id}/auto-invest",
            json={
                "contribution_amount": "150.00",
                "frequency": "biweekly",
                "next_contribution_date": next_date,
                "allocations": [
                    {"holding_id": str(h1.id), "ticker": "VTI", "percentage": "80.00"},
                ],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "100%" in resp.json()["detail"]

    def test_list_schedules(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        h1 = _make_holding(db_session, account.id, ticker="VTI", shares="10")
        schedule = _make_schedule(db_session, account.id, test_user.id)
        _make_allocation(db_session, schedule.id, h1.id, "VTI", 100)

        resp = client.get(f"/api/v1/portfolio/accounts/{account.id}/auto-invest", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_is_due_flag_true_when_past_due(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        h1 = _make_holding(db_session, account.id, ticker="VTI", shares="10")
        # Schedule with next_contribution_date in the past
        schedule = _make_schedule(db_session, account.id, test_user.id, days_until_due=-1)
        _make_allocation(db_session, schedule.id, h1.id, "VTI", 100)

        resp = client.get(f"/api/v1/portfolio/accounts/{account.id}/auto-invest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()[0]["is_due"] is True

    def test_is_due_flag_false_when_future(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        h1 = _make_holding(db_session, account.id, ticker="VTI", shares="10")
        schedule = _make_schedule(db_session, account.id, test_user.id, days_until_due=7)
        _make_allocation(db_session, schedule.id, h1.id, "VTI", 100)

        resp = client.get(f"/api/v1/portfolio/accounts/{account.id}/auto-invest", headers=auth_headers)
        assert resp.json()[0]["is_due"] is False

    def test_delete_schedule(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        h1 = _make_holding(db_session, account.id, ticker="VTI", shares="10")
        schedule = _make_schedule(db_session, account.id, test_user.id)
        _make_allocation(db_session, schedule.id, h1.id, "VTI", 100)

        resp = client.delete(f"/api/v1/portfolio/auto-invest/{schedule.id}", headers=auth_headers)
        assert resp.status_code == 204
        assert db_session.query(AutoInvestSchedule).filter_by(id=schedule.id).first() is None

    def test_cannot_access_other_users_schedule(self, client, auth_headers, db_session, test_user):
        other_user = _make_user(db_session, "scheother")
        other_account = _make_account(db_session, other_user.id)
        _make_holding(db_session, other_account.id, ticker="VTI", shares="10")
        schedule = _make_schedule(db_session, other_account.id, other_user.id)

        resp = client.delete(f"/api/v1/portfolio/auto-invest/{schedule.id}", headers=auth_headers)
        assert resp.status_code == 404


class TestAutoInvestApply:
    def test_apply_adds_shares_and_advances_date(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id, ticker="VTI", shares="10.000000")
        # Give holding a known price so apply can calculate shares
        holding.last_known_price = Decimal("250.00")
        db_session.commit()

        schedule = _make_schedule(db_session, account.id, test_user.id,
                                  contribution_amount="250.00", days_until_due=-1)
        _make_allocation(db_session, schedule.id, holding.id, "VTI", 100)

        # Mock the price fetcher to return $250
        mock_prices = {"VTI": Decimal("250.00")}
        with patch("app.api.v1.endpoints.portfolio.get_price_provider") as mock_provider_fn:
            mock_provider = mock_provider_fn.return_value
            mock_provider.fetch_prices = AsyncMock(return_value=mock_prices)

            resp = client.post(
                f"/api/v1/portfolio/auto-invest/{schedule.id}/apply",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["applied_amount"] == "250.00"
        assert len(data["shares_added"]) == 1
        assert data["shares_added"][0]["ticker"] == "VTI"

        # shares_added = 250 / 250 = 1.0 new shares → total should be 11.0
        db_session.refresh(holding)
        assert float(holding.shares) == pytest.approx(11.0)

        # next_contribution_date should advance by 2 weeks
        db_session.refresh(schedule)
        assert schedule.next_contribution_date == date.today() + timedelta(days=13)  # -1 + 14

    def test_apply_90_10_split(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        h1 = _make_holding(db_session, account.id, ticker="VTI", shares="10.000000")
        h2 = _make_holding(db_session, account.id, ticker="FZROX", shares="5.000000")
        h1.last_known_price = Decimal("200.00")
        h2.last_known_price = Decimal("100.00")
        db_session.commit()

        # $150 total: $135 → VTI, $15 → FZROX
        schedule = _make_schedule(db_session, account.id, test_user.id,
                                  contribution_amount="150.00", days_until_due=-1)
        _make_allocation(db_session, schedule.id, h1.id, "VTI", 90)
        _make_allocation(db_session, schedule.id, h2.id, "FZROX", 10)

        mock_prices = {"VTI": Decimal("200.00"), "FZROX": Decimal("100.00")}
        with patch("app.api.v1.endpoints.portfolio.get_price_provider") as mock_fn:
            mock_fn.return_value.fetch_prices = AsyncMock(return_value=mock_prices)
            resp = client.post(
                f"/api/v1/portfolio/auto-invest/{schedule.id}/apply",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        db_session.refresh(h1)
        db_session.refresh(h2)
        # VTI: 135/200 = 0.675 new shares
        assert float(h1.shares) == pytest.approx(10.675, abs=0.0001)
        # FZROX: 15/100 = 0.15 new shares
        assert float(h2.shares) == pytest.approx(5.15, abs=0.0001)

    def test_apply_fails_with_no_price(self, client, auth_headers, db_session, test_user):
        account = _make_account(db_session, test_user.id)
        holding = _make_holding(db_session, account.id, ticker="NOPRICE")
        # No last_known_price set

        schedule = _make_schedule(db_session, account.id, test_user.id, days_until_due=-1)
        _make_allocation(db_session, schedule.id, holding.id, "NOPRICE", 100)

        mock_prices: dict = {}
        with patch("app.api.v1.endpoints.portfolio.get_price_provider") as mock_fn:
            mock_fn.return_value.fetch_prices = AsyncMock(return_value=mock_prices)
            resp = client.post(
                f"/api/v1/portfolio/auto-invest/{schedule.id}/apply",
                headers=auth_headers,
            )

        assert resp.status_code == 422
        assert "No price available" in resp.json()["detail"]
