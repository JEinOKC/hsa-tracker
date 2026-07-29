"""HSA investment portfolio endpoints.

Endpoints:
  GET    /portfolio/accounts                                    - list user's HSA institution accounts
  POST   /portfolio/accounts                                    - create an account
  PATCH  /portfolio/accounts/{id}                               - update an account
  DELETE /portfolio/accounts/{id}                               - delete an account (cascades holdings)

  GET    /portfolio/accounts/{id}/holdings                      - list holdings for an account
  POST   /portfolio/accounts/{id}/holdings                      - add a holding
  PATCH  /portfolio/accounts/{id}/holdings/{hid}                - update a holding
  DELETE /portfolio/accounts/{id}/holdings/{hid}                - delete a holding

  GET    /portfolio/accounts/{id}/auto-invest                   - get auto-invest schedule for an account
  POST   /portfolio/accounts/{id}/auto-invest                   - create auto-invest schedule
  PATCH  /portfolio/auto-invest/{sid}                           - update schedule
  DELETE /portfolio/auto-invest/{sid}                           - delete schedule
  POST   /portfolio/auto-invest/{sid}/apply                     - apply next contribution (add shares)

  POST   /portfolio/prices/refresh                              - fetch current prices for all holdings
  GET    /portfolio/summary                                     - aggregate portfolio value
  GET    /portfolio/history                                     - daily portfolio value over time (for charts)
  GET    /portfolio/projection                                  - future-value projection
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.portfolio import (
    AutoInvestAllocation,
    AutoInvestSchedule,
    HoldingSnapshot,
    HsaAccount,
    HsaHolding,
)
from app.models.user import User
from app.schemas.portfolio import (
    AccountSummary,
    AutoInvestApplyResult,
    AutoInvestScheduleCreate,
    AutoInvestScheduleOut,
    AutoInvestScheduleUpdate,
    HsaAccountCreate,
    HsaAccountOut,
    HsaAccountUpdate,
    HsaHoldingCreate,
    HsaHoldingOut,
    HsaHoldingUpdate,
    PortfolioHistoryOut,
    PortfolioHistoryPoint,
    PortfolioSummaryOut,
    ProjectionOut,
    ProjectionPoint,
)
from app.services.price_fetcher import get_price_provider
from app.utils.access import check_permission, get_readable_owner_ids

router = APIRouter()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_account_or_404(account_id: UUID, owner_ids: list, db: Session) -> HsaAccount:
    account = (
        db.query(HsaAccount)
        .filter(HsaAccount.id == account_id, HsaAccount.user_id.in_(owner_ids))
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def _require_write(user: User, account: HsaAccount, db: Session) -> None:
    if not check_permission(user, account.user_id, "bank_accounts", "write", db):
        raise HTTPException(status_code=403, detail="Not allowed to modify this account")


def _upsert_snapshot(
    db: Session,
    holding: HsaHolding,
    user_id,
    price: Decimal,
    now: datetime,
) -> None:
    """Insert or update today's snapshot for a holding (one row per holding per day)."""
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    value = (holding.shares * price).quantize(Decimal("0.01"))

    existing = (
        db.query(HoldingSnapshot)
        .filter(
            HoldingSnapshot.holding_id == holding.id,
            HoldingSnapshot.snapshotted_at >= day_start,
            HoldingSnapshot.snapshotted_at <= day_end,
        )
        .first()
    )
    if existing:
        existing.shares = holding.shares
        existing.price = price
        existing.value = value
        existing.snapshotted_at = now
    else:
        db.add(HoldingSnapshot(
            holding_id=holding.id,
            account_id=holding.account_id,
            user_id=user_id,
            ticker=holding.ticker,
            shares=holding.shares,
            price=price,
            value=value,
            snapshotted_at=now,
        ))


# ─── Accounts ────────────────────────────────────────────────────────────────

@router.get("/accounts", response_model=List[HsaAccountOut])
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    return (
        db.query(HsaAccount)
        .filter(HsaAccount.user_id.in_(owner_ids), HsaAccount.is_active)
        .order_by(HsaAccount.created_at)
        .all()
    )


@router.post("/accounts", response_model=HsaAccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    body: HsaAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = HsaAccount(
        user_id=current_user.id,
        institution_name=body.institution_name,
        nickname=body.nickname,
        account_type=body.account_type,
        cash_balance=body.cash_balance,
        cash_balance_updated_at=datetime.utcnow() if body.cash_balance is not None else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.patch("/accounts/{account_id}", response_model=HsaAccountOut)
def update_account(
    account_id: UUID,
    body: HsaAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    account = _get_account_or_404(account_id, owner_ids, db)
    _require_write(current_user, account, db)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    if "cash_balance" in body.model_dump(exclude_unset=True):
        account.cash_balance_updated_at = datetime.utcnow()
    account.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    account = _get_account_or_404(account_id, owner_ids, db)
    _require_write(current_user, account, db)
    db.delete(account)
    db.commit()


# ─── Holdings ────────────────────────────────────────────────────────────────

@router.get("/accounts/{account_id}/holdings", response_model=List[HsaHoldingOut])
def list_holdings(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    account = _get_account_or_404(account_id, owner_ids, db)
    return account.holdings


@router.post("/accounts/{account_id}/holdings", response_model=HsaHoldingOut, status_code=status.HTTP_201_CREATED)
def add_holding(
    account_id: UUID,
    body: HsaHoldingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    account = _get_account_or_404(account_id, owner_ids, db)
    _require_write(current_user, account, db)

    holding = HsaHolding(
        account_id=account.id,
        ticker=body.ticker.upper().strip(),
        shares=body.shares,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


@router.patch("/accounts/{account_id}/holdings/{holding_id}", response_model=HsaHoldingOut)
def update_holding(
    account_id: UUID,
    holding_id: UUID,
    body: HsaHoldingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    account = _get_account_or_404(account_id, owner_ids, db)
    _require_write(current_user, account, db)

    holding = db.query(HsaHolding).filter(
        HsaHolding.id == holding_id, HsaHolding.account_id == account.id
    ).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")

    now = datetime.utcnow()
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "ticker" and value:
            value = value.upper().strip()
        setattr(holding, field, value)
    holding.updated_at = now

    # Snapshot if we have a price — captures the new share count against the latest price
    if holding.last_known_price is not None:
        _upsert_snapshot(db, holding, account.user_id, holding.last_known_price, now)

    db.commit()
    db.refresh(holding)
    return holding


@router.delete("/accounts/{account_id}/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(
    account_id: UUID,
    holding_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    account = _get_account_or_404(account_id, owner_ids, db)
    _require_write(current_user, account, db)

    holding = db.query(HsaHolding).filter(
        HsaHolding.id == holding_id, HsaHolding.account_id == account.id
    ).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")

    db.delete(holding)
    db.commit()


# ─── Price refresh ────────────────────────────────────────────────────────────

@router.post("/prices/refresh")
async def refresh_prices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch current prices for all of the user's holdings and update last_known_price."""
    owner_ids = get_readable_owner_ids(current_user, db)
    accounts = (
        db.query(HsaAccount)
        .options(joinedload(HsaAccount.holdings))
        .filter(HsaAccount.user_id.in_(owner_ids), HsaAccount.is_active)
        .all()
    )
    all_holdings: list[HsaHolding] = []
    for account in accounts:
        all_holdings.extend(account.holdings)

    if not all_holdings:
        return {"updated": 0}

    tickers = list({h.ticker for h in all_holdings})
    try:
        provider = get_price_provider()
        prices = await provider.fetch_prices(tickers)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    now = datetime.utcnow()
    account_by_id = {a.id: a for a in accounts}
    updated = 0
    not_found: list[str] = []
    for holding in all_holdings:
        price = prices.get(holding.ticker)
        if price is not None:
            holding.last_known_price = price
            holding.last_price_fetched_at = now
            holding.updated_at = now
            user_id = account_by_id[holding.account_id].user_id
            _upsert_snapshot(db, holding, user_id, price, now)
            updated += 1
        elif holding.ticker not in not_found:
            not_found.append(holding.ticker)

    db.commit()
    return {"updated": updated, "tickers_fetched": len(tickers), "not_found": not_found}


# ─── Summary ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=PortfolioSummaryOut)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    accounts = (
        db.query(HsaAccount)
        .filter(HsaAccount.user_id.in_(owner_ids), HsaAccount.is_active)
        .order_by(HsaAccount.created_at)
        .all()
    )

    account_summaries: list[AccountSummary] = []
    grand_total = Decimal("0")

    for account in accounts:
        cash = account.cash_balance or Decimal("0")
        invested = sum(
            (h.shares * h.last_known_price)
            for h in account.holdings
            if h.last_known_price is not None
        ) or Decimal("0")
        total = cash + invested

        # Only include total if we have at least one value to report
        has_data = account.cash_balance is not None or any(
            h.last_known_price is not None for h in account.holdings
        )

        account_summaries.append(AccountSummary(
            account_id=account.id,
            institution_name=account.institution_name,
            nickname=account.nickname,
            cash_balance=account.cash_balance,
            invested_value=invested if account.holdings else None,
            total_value=total if has_data else None,
            holdings_count=len(account.holdings),
            last_checkin_at=account.last_checkin_at,
        ))
        grand_total += total

    return PortfolioSummaryOut(
        accounts=account_summaries,
        total_value=grand_total if accounts else None,
    )


# ─── History ─────────────────────────────────────────────────────────────────

@router.get("/history", response_model=PortfolioHistoryOut)
def get_history(
    days: int = Query(default=90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return daily total holding value for the past N days, suitable for charting."""
    from sqlalchemy import func

    owner_ids = get_readable_owner_ids(current_user, db)
    cutoff = datetime.utcnow() - timedelta(days=days)

    # func.date() is supported by both SQLite (tests) and PostgreSQL (prod).
    # SQLite returns a string; PostgreSQL returns a datetime.date — str() normalises both.
    date_fn = func.date(HoldingSnapshot.snapshotted_at)

    # A holding can be snapshotted more than once in a day (e.g. two price
    # refreshes a few minutes apart).  Summing every row double-counts those
    # holdings and shows up as phantom growth on the chart, so rank each
    # holding's snapshots within its day and keep only the most recent.
    ranked = (
        db.query(
            date_fn.label("snap_date"),
            HoldingSnapshot.value.label("value"),
            func.row_number()
            .over(
                partition_by=[date_fn, HoldingSnapshot.holding_id],
                order_by=HoldingSnapshot.snapshotted_at.desc(),
            )
            .label("rn"),
        )
        .filter(
            HoldingSnapshot.user_id.in_(owner_ids),
            HoldingSnapshot.snapshotted_at >= cutoff,
        )
        .subquery()
    )

    rows = (
        db.query(
            ranked.c.snap_date,
            func.sum(ranked.c.value).label("total_value"),
        )
        .filter(ranked.c.rn == 1)
        .group_by(ranked.c.snap_date)
        .order_by(ranked.c.snap_date)
        .all()
    )

    return PortfolioHistoryOut(
        points=[
            PortfolioHistoryPoint(date=str(row.snap_date), total_value=row.total_value)
            for row in rows
        ]
    )


# ─── Projection ──────────────────────────────────────────────────────────────

@router.get("/projection", response_model=ProjectionOut)
def get_projection(
    years: int = Query(default=20, ge=1, le=50),
    annual_return: float = Query(default=7.0, ge=0.0, le=100.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate projected future value using FV = PV * (1 + r)^n."""
    owner_ids = get_readable_owner_ids(current_user, db)
    accounts = (
        db.query(HsaAccount)
        .filter(HsaAccount.user_id.in_(owner_ids), HsaAccount.is_active)
        .all()
    )

    # Starting value = sum of all cash + invested across all accounts
    starting = Decimal("0")
    for account in accounts:
        starting += account.cash_balance or Decimal("0")
        for h in account.holdings:
            if h.last_known_price is not None:
                starting += h.shares * h.last_known_price

    r = Decimal(str(annual_return / 100))
    points: list[ProjectionPoint] = []
    for year in range(0, years + 1):
        value = starting * ((1 + r) ** year)
        points.append(ProjectionPoint(year=year, value=value.quantize(Decimal("0.01"))))

    return ProjectionOut(
        starting_value=starting.quantize(Decimal("0.01")),
        annual_return=annual_return,
        points=points,
    )


# ─── Auto-Invest Schedule ─────────────────────────────────────────────────────

def _get_schedule_or_404(schedule_id: UUID, owner_ids: list, db: Session) -> AutoInvestSchedule:
    schedule = (
        db.query(AutoInvestSchedule)
        .filter(AutoInvestSchedule.id == schedule_id, AutoInvestSchedule.user_id.in_(owner_ids))
        .first()
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


def _schedule_out(schedule: AutoInvestSchedule) -> AutoInvestScheduleOut:
    return AutoInvestScheduleOut(
        id=schedule.id,
        account_id=schedule.account_id,
        contribution_amount=schedule.contribution_amount,
        frequency=schedule.frequency,
        next_contribution_date=schedule.next_contribution_date,
        is_active=schedule.is_active,
        is_due=schedule.next_contribution_date <= date.today(),
        allocations=schedule.allocations,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


@router.get("/accounts/{account_id}/auto-invest", response_model=List[AutoInvestScheduleOut])
def list_auto_invest_schedules(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    account = _get_account_or_404(account_id, owner_ids, db)
    schedules = (
        db.query(AutoInvestSchedule)
        .filter(AutoInvestSchedule.account_id == account.id)
        .options(joinedload(AutoInvestSchedule.allocations))
        .all()
    )
    return [_schedule_out(s) for s in schedules]


@router.post(
    "/accounts/{account_id}/auto-invest",
    response_model=AutoInvestScheduleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_auto_invest_schedule(
    account_id: UUID,
    body: AutoInvestScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    account = _get_account_or_404(account_id, owner_ids, db)
    _require_write(current_user, account, db)

    # Validate allocations sum to ~100%
    total_pct = sum(a.percentage for a in body.allocations)
    if abs(total_pct - Decimal("100")) > Decimal("0.01"):
        raise HTTPException(status_code=422, detail=f"Allocations must sum to 100% (got {total_pct}%)")

    if not body.allocations:
        raise HTTPException(status_code=422, detail="At least one allocation is required")

    now = datetime.utcnow()
    schedule = AutoInvestSchedule(
        account_id=account.id,
        user_id=current_user.id,
        contribution_amount=body.contribution_amount,
        frequency=body.frequency,
        next_contribution_date=body.next_contribution_date,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(schedule)
    db.flush()  # get schedule.id before creating allocations

    for alloc in body.allocations:
        db.add(AutoInvestAllocation(
            schedule_id=schedule.id,
            holding_id=alloc.holding_id,
            ticker=alloc.ticker.upper().strip(),
            percentage=alloc.percentage,
        ))

    db.commit()
    db.refresh(schedule)
    return _schedule_out(schedule)


@router.patch("/auto-invest/{schedule_id}", response_model=AutoInvestScheduleOut)
def update_auto_invest_schedule(
    schedule_id: UUID,
    body: AutoInvestScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    schedule = _get_schedule_or_404(schedule_id, owner_ids, db)
    account = _get_account_or_404(schedule.account_id, owner_ids, db)
    _require_write(current_user, account, db)

    update_data = body.model_dump(exclude_unset=True)
    allocations_data = update_data.pop("allocations", None)

    for field, value in update_data.items():
        setattr(schedule, field, value)
    schedule.updated_at = datetime.utcnow()

    if allocations_data is not None:
        total_pct = sum(a["percentage"] for a in allocations_data)
        if abs(Decimal(str(total_pct)) - Decimal("100")) > Decimal("0.01"):
            raise HTTPException(status_code=422, detail=f"Allocations must sum to 100% (got {total_pct}%)")
        # Replace all allocations
        for existing in schedule.allocations:
            db.delete(existing)
        db.flush()
        for alloc in allocations_data:
            db.add(AutoInvestAllocation(
                schedule_id=schedule.id,
                holding_id=alloc["holding_id"],
                ticker=alloc["ticker"].upper().strip(),
                percentage=alloc["percentage"],
            ))

    db.commit()
    db.refresh(schedule)
    return _schedule_out(schedule)


@router.delete("/auto-invest/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_auto_invest_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    schedule = _get_schedule_or_404(schedule_id, owner_ids, db)
    account = _get_account_or_404(schedule.account_id, owner_ids, db)
    _require_write(current_user, account, db)
    db.delete(schedule)
    db.commit()


@router.post("/auto-invest/{schedule_id}/apply", response_model=AutoInvestApplyResult)
async def apply_auto_invest(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Apply the next scheduled contribution.

    For each allocation, calculates shares = (amount * pct/100) / current_price
    and adds them to the holding. Advances next_contribution_date by the frequency interval.
    Requires holdings to have a current price (fetched or manually entered).
    """
    owner_ids = get_readable_owner_ids(current_user, db)
    schedule = _get_schedule_or_404(schedule_id, owner_ids, db)
    account = _get_account_or_404(schedule.account_id, owner_ids, db)
    _require_write(current_user, account, db)

    if not schedule.is_active:
        raise HTTPException(status_code=422, detail="Schedule is inactive")

    if not schedule.allocations:
        raise HTTPException(status_code=422, detail="Schedule has no allocations")

    # Collect holding objects, keyed by id
    holding_ids = [a.holding_id for a in schedule.allocations if a.holding_id]
    holdings_by_id = {
        h.id: h
        for h in db.query(HsaHolding).filter(HsaHolding.id.in_(holding_ids)).all()
    }

    # Refresh prices for tickers in this schedule so we get current values
    tickers = list({a.ticker for a in schedule.allocations})
    try:
        provider = get_price_provider()
        prices = await provider.fetch_prices(tickers)
    except RuntimeError:
        # Fall back to last_known_price if price fetch fails
        prices = {}

    now = datetime.utcnow()
    shares_added = []
    for alloc in schedule.allocations:
        holding = holdings_by_id.get(alloc.holding_id) if alloc.holding_id else None
        if holding is None:
            raise HTTPException(
                status_code=422,
                detail=f"Holding for {alloc.ticker} no longer exists. Update or delete this schedule.",
            )

        price = prices.get(alloc.ticker) or holding.last_known_price
        if price is None:
            raise HTTPException(
                status_code=422,
                detail=f"No price available for {alloc.ticker}. Refresh prices or enter manually first.",
            )

        dollar_amount = (schedule.contribution_amount * alloc.percentage / Decimal("100")).quantize(Decimal("0.01"))
        new_shares = (dollar_amount / price).quantize(Decimal("0.000001"))

        holding.shares = holding.shares + new_shares
        holding.last_known_price = price
        holding.last_price_fetched_at = now
        holding.updated_at = now

        _upsert_snapshot(db, holding, current_user.id, price, now)

        shares_added.append({
            "ticker": alloc.ticker,
            "shares_added": str(new_shares),
            "price_used": str(price),
            "dollar_amount": str(dollar_amount),
        })

    # Advance next_contribution_date
    current_date = schedule.next_contribution_date
    if schedule.frequency == "biweekly":
        next_date = current_date + timedelta(weeks=2)
    elif schedule.frequency == "weekly":
        next_date = current_date + timedelta(weeks=1)
    else:  # monthly
        # Advance by one month (same day)
        month = current_date.month + 1
        year = current_date.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        import calendar
        day = min(current_date.day, calendar.monthrange(year, month)[1])
        next_date = current_date.replace(year=year, month=month, day=day)

    schedule.next_contribution_date = next_date
    schedule.updated_at = now

    db.commit()

    return AutoInvestApplyResult(
        applied_amount=schedule.contribution_amount,
        shares_added=shares_added,
        next_contribution_date=next_date,
    )
