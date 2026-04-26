"""HSA investment portfolio endpoints.

Endpoints:
  GET    /portfolio/accounts                          - list user's HSA institution accounts
  POST   /portfolio/accounts                          - create an account
  PATCH  /portfolio/accounts/{id}                     - update an account
  DELETE /portfolio/accounts/{id}                     - delete an account (cascades holdings)

  GET    /portfolio/accounts/{id}/holdings            - list holdings for an account
  POST   /portfolio/accounts/{id}/holdings            - add a holding
  PATCH  /portfolio/accounts/{id}/holdings/{hid}      - update a holding
  DELETE /portfolio/accounts/{id}/holdings/{hid}      - delete a holding

  POST   /portfolio/prices/refresh                    - fetch current prices for all holdings
  GET    /portfolio/summary                           - aggregate portfolio value
  GET    /portfolio/projection                        - future-value projection
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.portfolio import HsaAccount, HsaHolding
from app.models.user import User
from app.schemas.portfolio import (
    HsaAccountCreate, HsaAccountOut, HsaAccountUpdate,
    HsaHoldingCreate, HsaHoldingOut, HsaHoldingUpdate,
    AccountSummary, PortfolioSummaryOut,
    ProjectionOut, ProjectionPoint,
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


# ─── Accounts ────────────────────────────────────────────────────────────────

@router.get("/accounts", response_model=List[HsaAccountOut])
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_ids = get_readable_owner_ids(current_user, db)
    return (
        db.query(HsaAccount)
        .filter(HsaAccount.user_id.in_(owner_ids), HsaAccount.is_active == True)
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

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "ticker" and value:
            value = value.upper().strip()
        setattr(holding, field, value)
    holding.updated_at = datetime.utcnow()

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
        .filter(HsaAccount.user_id.in_(owner_ids), HsaAccount.is_active == True)
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
    updated = 0
    not_found: list[str] = []
    for holding in all_holdings:
        price = prices.get(holding.ticker)
        if price is not None:
            holding.last_known_price = price
            holding.last_price_fetched_at = now
            holding.updated_at = now
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
        .filter(HsaAccount.user_id.in_(owner_ids), HsaAccount.is_active == True)
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
        .filter(HsaAccount.user_id.in_(owner_ids), HsaAccount.is_active == True)
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
