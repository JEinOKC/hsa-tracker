"""Manual transaction endpoints.

Allows users to create, update, and delete transactions that are not synced
from a bank provider (e.g. charges on a replaced/deactivated card).

Manual transactions use source='manual' and have no connection_id or
provider_transaction_id. They otherwise behave identically to Teller-synced
transactions and appear in the same transaction list views.
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.bank import BankConnection, BankTransaction
from app.models.user import User
from app.services.merchant_keywords import normalize_merchant_name
from app.services.rules_engine import (
    apply_auto_flag,
    apply_rules_to_transaction,
    get_active_rules_for_user,
)
from app.utils.access import get_readable_owner_ids
from app.api.v1.endpoints.bank import BankTransactionResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ManualTransactionCreate(BaseModel):
    transaction_date: date
    amount: Decimal  # positive value; stored as negative (debit) internally
    merchant_name: str
    description: Optional[str] = None


class ManualTransactionUpdate(BaseModel):
    transaction_date: Optional[date] = None
    amount: Optional[Decimal] = None
    merchant_name: Optional[str] = None
    description: Optional[str] = None


class MatchCandidate(BaseModel):
    """A Teller transaction that might match a manual entry the user is about to create."""
    id: UUID
    transaction_date: date
    amount: Decimal
    merchant_name: Optional[str]
    description: Optional[str]
    teller_category: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_manual_txn_or_404(txn_id: UUID, current_user: User, db: Session) -> BankTransaction:
    txn = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.id == txn_id,
            BankTransaction.source == "manual",
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Manual transaction not found")
    if txn.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this transaction")
    return txn


def _build_response(txn: BankTransaction) -> BankTransactionResponse:
    data = BankTransactionResponse.model_validate(txn)
    if txn.details and isinstance(txn.details, dict):
        cp = txn.details.get("counterparty") or {}
        if isinstance(cp, dict):
            data.teller_category = txn.details.get("category")
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/match", response_model=list[MatchCandidate])
async def find_matching_transactions(
    amount: Decimal = Query(..., description="Transaction amount (positive)"),
    txn_date: date = Query(..., alias="date", description="Transaction date"),
    merchant: Optional[str] = Query(None, description="Merchant name (optional, substring match)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find existing Teller transactions that might match a manual entry.

    Used before creating a manual transaction to prevent duplicates.
    Matches on amount (±5%) and date (±60 days), with optional merchant substring.
    Returns up to 5 results ordered by date proximity.
    """
    readable_owner_ids = get_readable_owner_ids(current_user, db, resource="transactions")
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(
            BankConnection.user_id.in_(readable_owner_ids),
            BankConnection.is_active == True,  # noqa: E712
        )
        .subquery()
    )

    from datetime import timedelta
    date_min = txn_date - timedelta(days=60)
    date_max = txn_date + timedelta(days=60)
    amount_neg = -abs(amount)  # stored as negative for debits
    tolerance = abs(amount) * Decimal("0.05")
    amount_min = amount_neg - tolerance
    amount_max = amount_neg + tolerance

    query = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.connection_id.in_(user_connection_ids),
            BankTransaction.source == "teller",
            BankTransaction.transaction_date >= date_min,
            BankTransaction.transaction_date <= date_max,
            BankTransaction.amount >= amount_min,
            BankTransaction.amount <= amount_max,
        )
    )

    if merchant:
        norm = normalize_merchant_name(merchant).lower()
        # Filter in Python after fetch (JSON field substring matching is awkward in SQLAlchemy)
        candidates = query.all()
        def _merchant_match(txn: BankTransaction) -> bool:
            details = txn.details or {}
            cp = details.get("counterparty") or {}
            name = cp.get("name") or txn.description or ""
            return norm in normalize_merchant_name(name).lower()
        candidates = [t for t in candidates if _merchant_match(t)]
    else:
        candidates = query.all()

    # Sort by date proximity
    candidates.sort(key=lambda t: abs((t.transaction_date - txn_date).days))
    candidates = candidates[:5]

    results = []
    for txn in candidates:
        details = txn.details or {}
        cp = details.get("counterparty") or {}
        merchant_name = cp.get("name") if isinstance(cp, dict) else None
        results.append(MatchCandidate(
            id=txn.id,
            transaction_date=txn.transaction_date,
            amount=abs(txn.amount),
            merchant_name=merchant_name,
            description=txn.description,
            teller_category=details.get("category"),
        ))
    return results


@router.post("/", response_model=BankTransactionResponse, status_code=201)
async def create_manual_transaction(
    payload: ManualTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a manually-entered transaction (e.g. from a replaced/deactivated card)."""
    txn = BankTransaction(
        id=uuid4(),
        source="manual",
        connection_id=None,
        provider="manual",
        provider_transaction_id=str(uuid4()),  # synthetic unique ID
        transaction_date=payload.transaction_date,
        amount=-abs(payload.amount),  # store as debit (negative)
        description=payload.description,
        transaction_type="manual",
        status="posted",
        details={"counterparty": {"name": payload.merchant_name}},
        user_id=current_user.id,
    )

    rules = get_active_rules_for_user(current_user.id, db)
    apply_auto_flag(txn)
    apply_rules_to_transaction(txn, rules)

    db.add(txn)
    db.commit()
    db.refresh(txn)
    return _build_response(txn)


@router.put("/{transaction_id}", response_model=BankTransactionResponse)
async def update_manual_transaction(
    transaction_id: UUID,
    payload: ManualTransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a manually-entered transaction. Returns 403 for provider-synced transactions."""
    txn = _get_manual_txn_or_404(transaction_id, current_user, db)

    if payload.transaction_date is not None:
        txn.transaction_date = payload.transaction_date
    if payload.amount is not None:
        txn.amount = -abs(payload.amount)
    if payload.merchant_name is not None:
        details = dict(txn.details or {})
        details["counterparty"] = {"name": payload.merchant_name}
        txn.details = details
    if payload.description is not None:
        txn.description = payload.description

    db.commit()
    db.refresh(txn)
    return _build_response(txn)


@router.delete("/{transaction_id}", status_code=204)
async def delete_manual_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a manually-entered transaction. Returns 403 for provider-synced transactions."""
    txn = _get_manual_txn_or_404(transaction_id, current_user, db)
    db.delete(txn)
    db.commit()
