"""Bank integration endpoints (Teller.io and future providers).

Endpoints:
  POST   /bank/connect                          - receive Teller Connect token, store + discover accounts
  GET    /bank/status                           - is a provider configured?
  GET    /bank/transactions                     - all transactions across all accounts (with filters)
  PATCH  /bank/transactions/{id}               - update HSA annotations on a transaction
  GET    /bank/accounts                         - list connected accounts (DB)
  GET    /bank/accounts/{id}                    - account details + live balance
  POST   /bank/accounts/{id}/sync              - sync transactions for one account
  GET    /bank/accounts/{id}/transactions      - list synced transactions for one account (DB)
  DELETE /bank/accounts/{id}                   - deactivate connection
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.bank import BankConnection, BankTransaction
from app.models.family import FamilyMember
from app.models.user import User
from app.providers import get_teller_provider, is_teller_configured

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class TellerEnrollment(BaseModel):
    """Payload sent from Teller Connect's onSuccess callback."""
    access_token: str


class BankStatusResponse(BaseModel):
    teller_configured: bool
    active_connections: int


class BankAccountResponse(BaseModel):
    id: UUID
    provider: str
    provider_account_id: str
    account_name: str
    account_type: Optional[str]
    account_subtype: Optional[str]
    institution_name: Optional[str]
    last_four: Optional[str]
    currency: str
    is_active: bool
    last_synced_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class BankAccountDetailResponse(BankAccountResponse):
    balance_ledger: Optional[Decimal] = None
    balance_available: Optional[Decimal] = None


class BankTransactionResponse(BaseModel):
    id: UUID
    connection_id: UUID
    provider: str
    provider_transaction_id: str
    transaction_date: date
    description: Optional[str]
    amount: Decimal
    transaction_type: Optional[str]
    status: str
    details: Optional[dict]
    created_at: datetime
    # HSA annotations
    is_hsa_eligible: Optional[bool]
    family_member_id: Optional[UUID]
    hsa_category: Optional[str]
    reimbursement_status: Optional[str]
    notes: Optional[str]
    # Denormalised for display
    account_name: Optional[str] = None
    institution_name: Optional[str] = None

    class Config:
        from_attributes = True


class BankTransactionAnnotation(BaseModel):
    """Partial update — only provided fields are changed."""
    is_hsa_eligible: Optional[bool] = None
    family_member_id: Optional[UUID] = None
    hsa_category: Optional[str] = None
    reimbursement_status: Optional[str] = None
    notes: Optional[str] = None


class SyncResult(BaseModel):
    added: int
    skipped: int
    account_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_connection_or_404(account_id: UUID, user_id, db: Session) -> BankConnection:
    connection = (
        db.query(BankConnection)
        .filter(BankConnection.id == account_id, BankConnection.user_id == user_id)
        .first()
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Bank account not found.")
    return connection


def _txn_to_response(txn: BankTransaction) -> BankTransactionResponse:
    """Map a BankTransaction ORM object to its response schema, adding denormalised fields."""
    data = BankTransactionResponse.model_validate(txn)
    if txn.connection:
        data.account_name = txn.connection.account_name
        data.institution_name = txn.connection.institution_name
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/connect", response_model=list[BankAccountResponse])
async def connect_bank(
    payload: TellerEnrollment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Receive a Teller Connect enrollment token, store it, and discover accounts.

    Called by the frontend immediately after the Teller Connect widget succeeds.
    Safe to call repeatedly — existing accounts are updated, not duplicated.
    """
    if not is_teller_configured():
        raise HTTPException(status_code=503, detail="Bank provider not configured.")

    provider = get_teller_provider(access_token=payload.access_token)
    external_accounts = provider.list_accounts()

    results = []
    for acct in external_accounts:
        existing = (
            db.query(BankConnection)
            .filter(
                BankConnection.provider == acct.provider,
                BankConnection.provider_account_id == acct.id,
            )
            .first()
        )
        if existing:
            existing.account_name = acct.name
            existing.account_type = acct.type
            existing.account_subtype = acct.subtype
            existing.institution_name = acct.institution_name
            existing.last_four = acct.last_four
            existing.enrollment_token = payload.access_token
            existing.user_id = current_user.id
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
            results.append(existing)
        else:
            connection = BankConnection(
                user_id=current_user.id,
                provider=acct.provider,
                provider_account_id=acct.id,
                account_name=acct.name,
                account_type=acct.type,
                account_subtype=acct.subtype,
                institution_name=acct.institution_name,
                last_four=acct.last_four,
                currency=acct.currency,
                enrollment_token=payload.access_token,
            )
            db.add(connection)
            results.append(connection)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


@router.get("/status", response_model=BankStatusResponse)
async def get_bank_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check whether a bank provider is configured and how many accounts are connected."""
    active = db.query(BankConnection).filter(BankConnection.is_active == True).count()
    return BankStatusResponse(
        teller_configured=is_teller_configured(),
        active_connections=active,
    )


class DashboardSummaryResponse(BaseModel):
    hsa_spending: float
    pending_reimbursement: float
    hsa_transaction_count: int
    has_family_members: bool
    has_bank_connections: bool
    has_synced_transactions: bool
    has_hsa_transactions: bool


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate stats for the dashboard, scoped to the given date range."""
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id == current_user.id, BankConnection.is_active == True)
        .subquery()
    )

    def date_filters():
        f = [
            BankTransaction.connection_id.in_(user_connection_ids),
            BankTransaction.is_hsa_eligible == True,
        ]
        if start_date:
            f.append(BankTransaction.transaction_date >= start_date)
        if end_date:
            f.append(BankTransaction.transaction_date <= end_date)
        return f

    hsa_spending = (
        db.query(func.sum(BankTransaction.amount))
        .filter(*date_filters())
        .scalar() or 0
    )

    pending = (
        db.query(func.sum(BankTransaction.amount))
        .filter(*date_filters(), BankTransaction.reimbursement_status.is_(None))
        .scalar() or 0
    )

    hsa_count = (
        db.query(func.count(BankTransaction.id))
        .filter(*date_filters())
        .scalar() or 0
    )

    has_family = db.query(FamilyMember).filter(FamilyMember.user_id == current_user.id).first() is not None
    has_connections = db.query(BankConnection).filter(
        BankConnection.user_id == current_user.id, BankConnection.is_active == True
    ).first() is not None
    has_transactions = db.query(BankTransaction).filter(
        BankTransaction.connection_id.in_(user_connection_ids)
    ).first() is not None

    return DashboardSummaryResponse(
        hsa_spending=float(hsa_spending),
        pending_reimbursement=float(pending),
        hsa_transaction_count=int(hsa_count),
        has_family_members=has_family,
        has_bank_connections=has_connections,
        has_synced_transactions=has_transactions,
        has_hsa_transactions=int(hsa_count) > 0,
    )


@router.get("/transactions", response_model=list[BankTransactionResponse])
async def list_all_transactions(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    is_hsa_eligible: Optional[bool] = Query(None, description="Filter by HSA eligibility (omit = all, true = HSA only, false = non-HSA only)"),
    family_member_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None, description="posted or pending"),
    search: Optional[str] = Query(None, description="Case-insensitive substring match on description"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all transactions across every connected account for the current user."""
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id == current_user.id, BankConnection.is_active == True)
        .subquery()
    )
    query = (
        db.query(BankTransaction)
        .filter(BankTransaction.connection_id.in_(user_connection_ids))
    )
    if start_date:
        query = query.filter(BankTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(BankTransaction.transaction_date <= end_date)
    if is_hsa_eligible is not None:
        query = query.filter(BankTransaction.is_hsa_eligible == is_hsa_eligible)
    if family_member_id:
        query = query.filter(BankTransaction.family_member_id == family_member_id)
    if status:
        query = query.filter(BankTransaction.status == status)
    if search:
        query = query.filter(BankTransaction.description.ilike(f"%{search}%"))

    txns = (
        query
        .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_txn_to_response(t) for t in txns]


@router.patch("/transactions/{transaction_id}", response_model=BankTransactionResponse)
async def annotate_transaction(
    transaction_id: UUID,
    payload: BankTransactionAnnotation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update HSA annotations on a transaction (is_hsa_eligible, family member, category, etc.)."""
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id == current_user.id)
        .subquery()
    )
    txn = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.id == transaction_id,
            BankTransaction.connection_id.in_(user_connection_ids),
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)

    db.commit()
    db.refresh(txn)
    return _txn_to_response(txn)


@router.get("/accounts", response_model=list[BankAccountResponse])
async def list_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all connected bank accounts stored in the database."""
    return (
        db.query(BankConnection)
        .filter(BankConnection.user_id == current_user.id, BankConnection.is_active == True)
        .all()
    )


@router.get("/accounts/{account_id}", response_model=BankAccountDetailResponse)
async def get_bank_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a connected account's details plus its live balance from the provider."""
    connection = _get_connection_or_404(account_id, current_user.id, db)
    response = BankAccountDetailResponse.model_validate(connection)

    if is_teller_configured() and connection.enrollment_token:
        try:
            provider = get_teller_provider(access_token=connection.enrollment_token)
            balance = provider.get_balance(connection.provider_account_id)
            response.balance_ledger = balance.ledger
            response.balance_available = balance.available
        except Exception:
            pass  # Return account data without balance if live fetch fails

    return response


@router.post("/accounts/{account_id}/sync", response_model=SyncResult)
async def sync_account_transactions(
    account_id: UUID,
    from_date: Optional[date] = Query(None, description="Only fetch transactions on or after this date"),
    count: int = Query(250, le=500, description="Max transactions to fetch from provider"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch recent transactions from the provider and store new ones.

    Existing transactions (matched by provider_transaction_id) are skipped.
    """
    connection = _get_connection_or_404(account_id, current_user.id, db)

    if not is_teller_configured():
        raise HTTPException(status_code=503, detail="Bank provider not configured.")
    if not connection.enrollment_token:
        raise HTTPException(status_code=422, detail="Account has no enrollment token. Reconnect via Teller Connect.")

    provider = get_teller_provider(access_token=connection.enrollment_token)
    external_txns = provider.list_transactions(
        connection.provider_account_id,
        from_date=from_date,
        count=count,
    )

    added = 0
    skipped = 0
    for txn in external_txns:
        exists = (
            db.query(BankTransaction)
            .filter(
                BankTransaction.connection_id == connection.id,
                BankTransaction.provider_transaction_id == txn.id,
            )
            .first()
        )
        if exists:
            skipped += 1
            continue

        db.add(BankTransaction(
            connection_id=connection.id,
            provider=txn.provider,
            provider_transaction_id=txn.id,
            transaction_date=txn.date,
            description=txn.description,
            amount=txn.amount,
            transaction_type=txn.type,
            status=txn.status,
            details=txn.details,
        ))
        added += 1

    connection.last_synced_at = datetime.utcnow()
    db.commit()

    return SyncResult(added=added, skipped=skipped, account_id=str(account_id))


@router.get("/accounts/{account_id}/transactions", response_model=list[BankTransactionResponse])
async def list_account_transactions(
    account_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None, description="Filter by status: posted, pending"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List transactions stored in the database for a connected account."""
    connection = _get_connection_or_404(account_id, current_user.id, db)

    query = db.query(BankTransaction).filter(BankTransaction.connection_id == account_id)

    if start_date:
        query = query.filter(BankTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(BankTransaction.transaction_date <= end_date)
    if status:
        query = query.filter(BankTransaction.status == status)

    return (
        query
        .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.delete("/accounts/{account_id}", status_code=204)
async def disconnect_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a bank connection (keeps historical transactions)."""
    connection = _get_connection_or_404(account_id, current_user.id, db)
    connection.is_active = False
    connection.updated_at = datetime.utcnow()
    db.commit()
