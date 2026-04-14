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
from app.models.bank import BankConnection, BankTransaction, TransactionDocument
from app.models.family import FamilyMember
from app.models.household import HouseholdMembership
from app.models.user import User
from app.providers import get_teller_provider, is_teller_configured
from app.utils.access import get_readable_owner_ids, check_permission
from app.services.rules_engine import apply_auto_flag, apply_rules_to_transaction, get_active_rules_for_user

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
    owner_display_name: Optional[str] = None  # Set for shared accounts

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
    # Document attachment count (confirmed uploads only)
    document_count: int = 0
    # Reimbursement timestamp
    reimbursed_at: Optional[datetime] = None
    # Set for transactions from shared accounts
    owner_display_name: Optional[str] = None
    # Rules engine fields
    auto_flag: Optional[str] = None
    rule_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class BankTransactionAnnotation(BaseModel):
    """Partial update — only provided fields are changed."""
    is_hsa_eligible: Optional[bool] = None
    family_member_id: Optional[UUID] = None
    hsa_category: Optional[str] = None
    reimbursement_status: Optional[str] = None
    reimbursed_at: Optional[datetime] = None
    notes: Optional[str] = None


class SyncResult(BaseModel):
    added: int
    skipped: int
    account_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_connection_or_404(account_id: UUID, user, db: Session, operation: str = "read") -> BankConnection:
    connection = db.query(BankConnection).filter(BankConnection.id == account_id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Bank account not found.")
    if not check_permission(user, connection.user_id, "bank_accounts", operation, db):
        raise HTTPException(status_code=403, detail="Access denied.")
    return connection


def _txn_to_response(txn: BankTransaction, document_count: int = 0, owner_display_name: Optional[str] = None) -> BankTransactionResponse:
    """Map a BankTransaction ORM object to its response schema, adding denormalised fields."""
    data = BankTransactionResponse.model_validate(txn)
    if txn.connection:
        data.account_name = txn.connection.account_name
        data.institution_name = txn.connection.institution_name
    data.document_count = document_count
    data.owner_display_name = owner_display_name
    return data


def _batch_document_counts(txn_ids: list, db: Session) -> dict:
    """Return a {transaction_id: count} dict for the given transaction IDs (confirmed only)."""
    if not txn_ids:
        return {}
    rows = (
        db.query(TransactionDocument.transaction_id, func.count(TransactionDocument.id))
        .filter(
            TransactionDocument.transaction_id.in_(txn_ids),
            TransactionDocument.status == "confirmed",
        )
        .group_by(TransactionDocument.transaction_id)
        .all()
    )
    return {row[0]: row[1] for row in rows}


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
    undocumented_hsa_count: int
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
    readable_owner_ids = get_readable_owner_ids(current_user, db, resource="transactions")
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id.in_(readable_owner_ids), BankConnection.is_active == True)
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

    confirmed_doc_txn_ids = (
        db.query(TransactionDocument.transaction_id)
        .filter(TransactionDocument.status == "confirmed")
        .subquery()
    )
    undocumented_count = (
        db.query(func.count(BankTransaction.id))
        .filter(*date_filters(), ~BankTransaction.id.in_(confirmed_doc_txn_ids))
        .scalar() or 0
    )

    membership = db.query(HouseholdMembership).filter(HouseholdMembership.user_id == current_user.id).first()
    has_family = membership is not None and db.query(FamilyMember).filter(
        FamilyMember.household_id == membership.household_id
    ).first() is not None
    readable_bank_ids = get_readable_owner_ids(current_user, db, resource="bank_accounts")
    has_connections = db.query(BankConnection).filter(
        BankConnection.user_id.in_(readable_bank_ids), BankConnection.is_active == True
    ).first() is not None
    has_transactions = db.query(BankTransaction).filter(
        BankTransaction.connection_id.in_(user_connection_ids)
    ).first() is not None

    return DashboardSummaryResponse(
        hsa_spending=float(hsa_spending),
        pending_reimbursement=float(pending),
        hsa_transaction_count=int(hsa_count),
        undocumented_hsa_count=int(undocumented_count),
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
    reimbursement_status: Optional[str] = Query(None, description="Filter by reimbursement status (e.g. 'reimbursed', 'null' for unset)"),
    has_documents: Optional[bool] = Query(None, description="Filter by documentation status (true = has receipts, false = missing receipts)"),
    search: Optional[str] = Query(None, description="Case-insensitive substring match on description"),
    show_hidden: bool = Query(False, description="Include transactions flagged as hidden (default: excluded)"),
    auto_flag_filter: Optional[str] = Query(None, alias="auto_flag", description="Filter to transactions with this auto_flag value"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all transactions across every connected account for the current user and shared accounts."""
    readable_owner_ids = get_readable_owner_ids(current_user, db, resource="transactions")
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id.in_(readable_owner_ids), BankConnection.is_active == True)
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
    if reimbursement_status == 'null':
        query = query.filter(BankTransaction.reimbursement_status.is_(None))
    elif reimbursement_status:
        query = query.filter(BankTransaction.reimbursement_status == reimbursement_status)
    if has_documents is not None:
        confirmed_doc_subq = (
            db.query(TransactionDocument.transaction_id)
            .filter(TransactionDocument.status == "confirmed")
            .subquery()
        )
        if has_documents:
            query = query.filter(BankTransaction.id.in_(confirmed_doc_subq))
        else:
            query = query.filter(~BankTransaction.id.in_(confirmed_doc_subq))
    if search:
        query = query.filter(BankTransaction.description.ilike(f"%{search}%"))
    if not show_hidden:
        query = query.filter(
            (BankTransaction.auto_flag != "hidden") | BankTransaction.auto_flag.is_(None)
        )
    if auto_flag_filter is not None:
        query = query.filter(BankTransaction.auto_flag == auto_flag_filter)

    txns = (
        query
        .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    counts = _batch_document_counts([t.id for t in txns], db)

    # Build owner lookup for attribution
    owner_map: dict = {}
    from app.models.user import User as UserModel
    for txn in txns:
        owner_id = txn.connection.user_id if txn.connection else None
        if owner_id and owner_id != current_user.id and owner_id not in owner_map:
            owner = db.query(UserModel).filter(UserModel.id == owner_id).first()
            owner_map[owner_id] = owner.display_name if owner else None

    def _owner_name(txn):
        owner_id = txn.connection.user_id if txn.connection else None
        if owner_id and owner_id != current_user.id:
            return owner_map.get(owner_id)
        return None

    return [_txn_to_response(t, counts.get(t.id, 0), _owner_name(t)) for t in txns]


@router.patch("/transactions/{transaction_id}", response_model=BankTransactionResponse)
async def annotate_transaction(
    transaction_id: UUID,
    payload: BankTransactionAnnotation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update HSA annotations on a transaction (is_hsa_eligible, family member, category, etc.)."""
    readable_owner_ids = get_readable_owner_ids(current_user, db, resource="transactions")
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id.in_(readable_owner_ids))
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

    # Check write permission on the transaction's owner
    connection = db.query(BankConnection).filter(BankConnection.id == txn.connection_id).first()
    if connection and not check_permission(current_user, connection.user_id, "transactions", "write", db):
        raise HTTPException(status_code=403, detail="Write access denied.")

    updates = payload.model_dump(exclude_unset=True)

    # Auto-set reimbursed_at when marking as reimbursed (unless caller provides one explicitly)
    if updates.get("reimbursement_status") == "reimbursed" and "reimbursed_at" not in updates:
        updates["reimbursed_at"] = datetime.utcnow()
    # Clear reimbursed_at when status is removed
    elif "reimbursement_status" in updates and updates["reimbursement_status"] != "reimbursed":
        updates.setdefault("reimbursed_at", None)

    for field, value in updates.items():
        setattr(txn, field, value)

    db.commit()
    db.refresh(txn)
    doc_count = (
        db.query(func.count(TransactionDocument.id))
        .filter(
            TransactionDocument.transaction_id == txn.id,
            TransactionDocument.status == "confirmed",
        )
        .scalar() or 0
    )
    return _txn_to_response(txn, doc_count)


@router.get("/accounts", response_model=list[BankAccountResponse])
async def list_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all connected bank accounts for current user and shared accounts."""
    readable_owner_ids = get_readable_owner_ids(current_user, db, resource="bank_accounts")
    connections = (
        db.query(BankConnection)
        .filter(BankConnection.user_id.in_(readable_owner_ids), BankConnection.is_active == True)
        .all()
    )
    # Build owner lookup for attribution
    owner_cache: dict = {}
    from app.models.user import User as UserModel
    result = []
    for conn in connections:
        resp = BankAccountResponse.model_validate(conn)
        if conn.user_id != current_user.id:
            if conn.user_id not in owner_cache:
                owner = db.query(UserModel).filter(UserModel.id == conn.user_id).first()
                owner_cache[conn.user_id] = owner.display_name if owner else None
            resp.owner_display_name = owner_cache[conn.user_id]
        result.append(resp)
    return result


@router.get("/accounts/{account_id}", response_model=BankAccountDetailResponse)
async def get_bank_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a connected account's details plus its live balance from the provider."""
    connection = _get_connection_or_404(account_id, current_user, db)
    response = BankAccountDetailResponse.model_validate(connection)
    if connection.user_id != current_user.id:
        from app.models.user import User as UserModel
        owner = db.query(UserModel).filter(UserModel.id == connection.user_id).first()
        response.owner_display_name = owner.display_name if owner else None

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
    connection = _get_connection_or_404(account_id, current_user, db, operation="write")

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
    new_txns = []
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

        # Teller uses accounting sign convention for credit accounts: purchases
        # are positive (balance increases) and payments are negative.  Our
        # internal convention is negative = expense, positive = credit/refund,
        # which matches depository accounts directly.  Negate for credit accounts.
        amount = -txn.amount if connection.account_type == "credit" else txn.amount

        new_txn = BankTransaction(
            connection_id=connection.id,
            provider=txn.provider,
            provider_transaction_id=txn.id,
            transaction_date=txn.date,
            description=txn.description,
            amount=amount,
            transaction_type=txn.type,
            status=txn.status,
            details=txn.details,
        )
        db.add(new_txn)
        new_txns.append(new_txn)
        added += 1

    if new_txns:
        db.flush()  # assign IDs before running rules
        rules = get_active_rules_for_user(current_user.id, db)
        for new_txn in new_txns:
            apply_auto_flag(new_txn)
            apply_rules_to_transaction(new_txn, rules)

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
    connection = _get_connection_or_404(account_id, current_user, db)

    query = db.query(BankTransaction).filter(BankTransaction.connection_id == account_id)

    if start_date:
        query = query.filter(BankTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(BankTransaction.transaction_date <= end_date)
    if status:
        query = query.filter(BankTransaction.status == status)

    txns = (
        query
        .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    counts = _batch_document_counts([t.id for t in txns], db)
    return [_txn_to_response(t, counts.get(t.id, 0)) for t in txns]


@router.delete("/accounts/{account_id}", status_code=204)
async def disconnect_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a bank connection (keeps historical transactions)."""
    connection = _get_connection_or_404(account_id, current_user, db, operation="delete")
    connection.is_active = False
    connection.updated_at = datetime.utcnow()
    db.commit()
