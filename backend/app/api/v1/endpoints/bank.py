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

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.bank import BankConnection, BankTransaction, TransactionDocument, UserCategoryOverride
from app.models.family import FamilyMember, HsaEligibilityPeriod
from app.models.household import Household, HouseholdMembership
from app.models.user import User
from app.providers import get_teller_provider, is_teller_configured
from app.utils.access import get_readable_owner_ids, check_permission
from app.services.rules_engine import (
    apply_auto_flag, apply_rules_to_transaction, get_active_rules_for_user,
    get_smart_hidden_categories, NON_HSA_CATEGORIES, SMART_DEFAULT_HIDDEN,
    _SMART_MIN_REVIEWED, _SMART_MIN_HSA_RATE,
)
from app.services.merchant_keywords import classify_merchant, normalize_merchant_name

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
    connection_id: Optional[UUID]
    source: str = "teller"
    provider: Optional[str]
    provider_transaction_id: Optional[str]
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
    eligible_amount: Optional[Decimal] = None
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
    # Coverage window
    eligibility_warning: bool = False
    # Teller-provided category (extracted from details JSON for convenience)
    teller_category: Optional[str] = None

    class Config:
        from_attributes = True


class MerchantSummary(BaseModel):
    """Aggregated view of a single normalized merchant across all transactions."""
    normalized_name: str
    transaction_count: int
    total_amount: Decimal
    first_seen: date
    last_seen: date
    has_hsa: bool
    hsa_likelihood: str  # 'likely' | 'unlikely' | 'unknown'


class BankTransactionAnnotation(BaseModel):
    """Partial update — only provided fields are changed."""
    is_hsa_eligible: Optional[bool] = None
    family_member_id: Optional[UUID] = None
    hsa_category: Optional[str] = None
    eligible_amount: Optional[Decimal] = None
    reimbursement_status: Optional[str] = None
    reimbursed_at: Optional[datetime] = None
    notes: Optional[str] = None
    auto_flag: Optional[str] = None


class SyncResult(BaseModel):
    added: int
    skipped: int
    account_id: str
    potential_hsa_count: int = 0


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


def _txn_to_response(
    txn: BankTransaction,
    document_count: int = 0,
    owner_display_name: Optional[str] = None,
    eligibility_warning: bool = False,
) -> BankTransactionResponse:
    """Map a BankTransaction ORM object to its response schema, adding denormalised fields."""
    data = BankTransactionResponse.model_validate(txn)
    if txn.connection:
        data.account_name = txn.connection.account_name
        data.institution_name = txn.connection.institution_name
    data.document_count = document_count
    data.owner_display_name = owner_display_name
    data.eligibility_warning = eligibility_warning
    if txn.details and isinstance(txn.details, dict):
        data.teller_category = txn.details.get("category")
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


def _load_member_periods(household_id, db: Session) -> dict:
    """Return {member_id: [(start_date, end_date), ...]} for all members in a household."""
    members = (
        db.query(FamilyMember)
        .filter(FamilyMember.household_id == household_id)
        .all()
    )
    member_ids = [m.id for m in members]
    if not member_ids:
        return {}
    periods = (
        db.query(HsaEligibilityPeriod)
        .filter(HsaEligibilityPeriod.family_member_id.in_(member_ids))
        .all()
    )
    result: dict = {m.id: [] for m in members}
    for p in periods:
        result[p.family_member_id].append((p.start_date, p.end_date))
    return result


def _earliest_hsa_start(household_id, db: Session) -> Optional[date]:
    """Return the earliest HSA eligibility start date across all members in the household."""
    members = (
        db.query(FamilyMember)
        .filter(FamilyMember.household_id == household_id)
        .all()
    )
    member_ids = [m.id for m in members]
    if not member_ids:
        return None
    result = (
        db.query(func.min(HsaEligibilityPeriod.start_date))
        .filter(HsaEligibilityPeriod.family_member_id.in_(member_ids))
        .scalar()
    )
    return result


def _is_eligible(member_periods: dict, family_member_id, txn_date) -> bool:
    """Return True if the transaction date falls within the member's coverage window."""
    if family_member_id is None:
        return False
    periods = member_periods.get(family_member_id, [])
    if not periods:
        return False
    return any(
        p_start <= txn_date and (p_end is None or p_end >= txn_date)
        for p_start, p_end in periods
    )


def _get_user_household(user_id, db: Session):
    """Return the Household for this user, or None."""
    mem = db.query(HouseholdMembership).filter(HouseholdMembership.user_id == user_id).first()
    if not mem:
        return None
    return db.query(Household).filter(Household.id == mem.household_id).first()


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

    # Strict eligibility: only count transactions within a member's coverage window
    household = _get_user_household(current_user.id, db)
    strict = household.strict_eligibility if household else False

    def date_filters():
        f = [
            BankTransaction.connection_id.in_(user_connection_ids),
            BankTransaction.is_hsa_eligible == True,
        ]
        if start_date:
            f.append(BankTransaction.transaction_date >= start_date)
        if end_date:
            f.append(BankTransaction.transaction_date <= end_date)
        if strict:
            # Must have an assigned member
            f.append(BankTransaction.family_member_id.isnot(None))
            # That member must have an eligibility period covering the transaction date
            eligible_exists = (
                db.query(HsaEligibilityPeriod.id)
                .filter(
                    HsaEligibilityPeriod.family_member_id == BankTransaction.family_member_id,
                    HsaEligibilityPeriod.start_date <= BankTransaction.transaction_date,
                    or_(
                        HsaEligibilityPeriod.end_date.is_(None),
                        HsaEligibilityPeriod.end_date >= BankTransaction.transaction_date,
                    ),
                )
                .correlate(BankTransaction)
                .exists()
            )
            f.append(eligible_exists)
        return f

    # Use eligible_amount when set (partial charges), otherwise fall back to full amount
    _effective_amount = func.coalesce(BankTransaction.eligible_amount, BankTransaction.amount)

    hsa_spending = (
        db.query(func.sum(_effective_amount))
        .filter(*date_filters())
        .scalar() or 0
    )

    pending = (
        db.query(func.sum(_effective_amount))
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


@router.get("/smart-filter/status")
async def get_smart_filter_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return Smart filter status for every category the user has transactions in."""
    from app.models.bank import BankConnection as BC

    user_connection_ids = (
        db.query(BC.id)
        .filter(BC.user_id == current_user.id, BC.is_active == True)  # noqa: E712
        .subquery()
    )

    # Per-category HSA stats
    rows = (
        db.query(
            BankTransaction.details["category"].astext.label("category"),
            func.count().filter(BankTransaction.is_hsa_eligible.isnot(None)).label("reviewed"),
            func.count().filter(BankTransaction.is_hsa_eligible == True).label("hsa_count"),  # noqa: E712
        )
        .filter(
            BankTransaction.connection_id.in_(user_connection_ids),
            BankTransaction.details["category"].astext.isnot(None),
        )
        .group_by(BankTransaction.details["category"].astext)
        .all()
    )

    overrides = {
        o.category: o.pin_mode
        for o in db.query(UserCategoryOverride).filter(UserCategoryOverride.user_id == current_user.id).all()
    }

    result = []
    for row in rows:
        cat = row.category
        if not cat:
            continue
        reviewed = row.reviewed or 0
        hsa_count = row.hsa_count or 0
        hsa_rate = (hsa_count / reviewed) if reviewed > 0 else 0.0
        is_auto_promoted = reviewed >= _SMART_MIN_REVIEWED and hsa_rate >= _SMART_MIN_HSA_RATE
        is_hidden_by_default = cat in SMART_DEFAULT_HIDDEN
        pin_mode = overrides.get(cat)

        if pin_mode == "show":
            effective_hidden = False
        elif pin_mode == "hide":
            effective_hidden = True
        elif is_auto_promoted:
            effective_hidden = False
        else:
            effective_hidden = is_hidden_by_default

        result.append({
            "category": cat,
            "is_hidden_by_default": is_hidden_by_default,
            "is_auto_promoted": is_auto_promoted,
            "pin_mode": pin_mode,
            "effective_smart_hidden": effective_hidden,
            "reviewed_count": reviewed,
            "hsa_rate": round(hsa_rate, 4),
        })

    return sorted(result, key=lambda r: r["category"])


@router.put("/smart-filter/categories/{category}", status_code=200)
async def set_category_smart_override(
    category: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pin a category to always show or always hide in Smart filter mode."""
    pin_mode = body.get("pin_mode")
    if pin_mode not in ("show", "hide"):
        raise HTTPException(status_code=422, detail="pin_mode must be 'show' or 'hide'")

    existing = (
        db.query(UserCategoryOverride)
        .filter(UserCategoryOverride.user_id == current_user.id, UserCategoryOverride.category == category)
        .first()
    )
    if existing:
        existing.pin_mode = pin_mode
    else:
        db.add(UserCategoryOverride(user_id=current_user.id, category=category, pin_mode=pin_mode))
    db.commit()
    return {"category": category, "pin_mode": pin_mode}


@router.delete("/smart-filter/categories/{category}", status_code=204)
async def delete_category_smart_override(
    category: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a category pin, reverting to auto Smart filter behavior."""
    db.query(UserCategoryOverride).filter(
        UserCategoryOverride.user_id == current_user.id,
        UserCategoryOverride.category == category,
    ).delete()
    db.commit()


@router.get("/transactions/categories", response_model=list[str])
async def list_transaction_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return distinct Teller category values present in the user's transactions."""
    readable_owner_ids = get_readable_owner_ids(current_user, db, resource="transactions")
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id.in_(readable_owner_ids), BankConnection.is_active == True)
        .subquery()
    )
    rows = (
        db.query(BankTransaction.details["category"].astext)
        .filter(
            BankTransaction.connection_id.in_(user_connection_ids),
            BankTransaction.details["category"].astext.isnot(None),
        )
        .distinct()
        .all()
    )
    return sorted(r[0] for r in rows if r[0])


@router.get("/transactions/merchants", response_model=list[MerchantSummary])
async def list_transaction_merchants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return merchants grouped and normalized, sorted by transaction count descending.

    Merchant names are normalized (store numbers stripped) and grouped so that
    'MCDONALD'S #4829' and 'MCDONALD'S #3021' appear as a single 'MCDONALD'S' entry.
    Each entry includes an hsa_likelihood classification ('likely', 'unlikely', 'unknown')
    and a has_hsa flag (true if any transaction from that merchant is marked HSA-eligible).
    Hidden transactions are excluded.
    """
    readable_owner_ids = get_readable_owner_ids(current_user, db, resource="transactions")
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id.in_(readable_owner_ids), BankConnection.is_active == True)
        .subquery()
    )

    # Fetch all non-hidden transactions. Extract counterparty name in Python to
    # stay compatible with both PostgreSQL and SQLite (JSON path syntax differs).
    txns = (
        db.query(
            BankTransaction.details,
            BankTransaction.description,
            BankTransaction.amount,
            BankTransaction.transaction_date,
            BankTransaction.is_hsa_eligible,
        )
        .filter(
            (BankTransaction.connection_id.in_(user_connection_ids)) |
            (BankTransaction.source == "manual"),
            (BankTransaction.auto_flag != "hidden") | (BankTransaction.auto_flag.is_(None)),
        )
        .all()
    )

    # Group by normalized name in Python
    from collections import defaultdict
    from decimal import Decimal as D

    groups: dict[str, dict] = defaultdict(lambda: {
        "total_amount": D("0"),
        "count": 0,
        "first_seen": None,
        "last_seen": None,
        "has_hsa": False,
    })

    for details, description, amount, txn_date, is_hsa in txns:
        cp = (details or {}).get("counterparty") or {}
        raw_name = (cp.get("name") if isinstance(cp, dict) else None) or description
        if not raw_name:
            continue
        normalized = normalize_merchant_name(raw_name)
        if not normalized:
            continue
        g = groups[normalized]
        g["count"] += 1
        g["total_amount"] += abs(amount or D("0"))
        if g["first_seen"] is None or txn_date < g["first_seen"]:
            g["first_seen"] = txn_date
        if g["last_seen"] is None or txn_date > g["last_seen"]:
            g["last_seen"] = txn_date
        if is_hsa:
            g["has_hsa"] = True

    results = [
        MerchantSummary(
            normalized_name=name,
            transaction_count=g["count"],
            total_amount=g["total_amount"],
            first_seen=g["first_seen"],
            last_seen=g["last_seen"],
            has_hsa=g["has_hsa"],
            hsa_likelihood=classify_merchant(name),
        )
        for name, g in groups.items()
        if g["first_seen"] is not None
    ]

    # Sort: unlikely first (by count desc), then unknown, then likely last
    likelihood_order = {"unlikely": 0, "unknown": 1, "likely": 2}
    results.sort(key=lambda m: (likelihood_order[m.hsa_likelihood], -m.transaction_count))
    return results


def _build_transaction_query(
    db: Session,
    user_connection_ids,
    *,
    current_user_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_hsa_eligible: Optional[bool] = None,
    include_potential_hsa: bool = False,
    family_member_id: Optional[UUID] = None,
    status: Optional[str] = None,
    reimbursement_status: Optional[str] = None,
    has_documents: Optional[bool] = None,
    search: Optional[str] = None,
    show_hidden: bool = False,
    show_all_categories: bool = False,
    auto_flag_filter: Optional[str] = None,
    teller_category: Optional[str] = None,
):
    """Return a filtered SQLAlchemy query for BankTransaction (no limit/offset applied).

    Includes both provider-synced transactions (via connection_id) and manual
    transactions owned directly by current_user_id.
    """
    ownership_filter = BankTransaction.connection_id.in_(user_connection_ids)
    if current_user_id is not None:
        ownership_filter = or_(
            ownership_filter,
            (BankTransaction.source == "manual") & (BankTransaction.user_id == current_user_id),
        )
    query = db.query(BankTransaction).filter(ownership_filter)
    if start_date:
        query = query.filter(BankTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(BankTransaction.transaction_date <= end_date)
    if is_hsa_eligible is not None:
        if is_hsa_eligible and include_potential_hsa:
            # Confirmed HSA eligible OR unreviewed auto-flagged as potential
            query = query.filter(
                (BankTransaction.is_hsa_eligible == True) |  # noqa: E712
                (
                    BankTransaction.is_hsa_eligible.is_(None) &
                    (BankTransaction.auto_flag == "potential_hsa")
                )
            )
        else:
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
        # In "Smart" mode (default), exclude unreviewed transactions in categories
        # the adaptive filter says to hide. "All" mode bypasses this entirely.
        # Transactions with no category (NULL) always show.
        if not show_all_categories and teller_category is None and current_user_id is not None:
            smart_hidden = get_smart_hidden_categories(current_user_id, db)
            if smart_hidden:
                category_col = BankTransaction.details["category"].astext
                query = query.filter(
                    BankTransaction.is_hsa_eligible.isnot(None) |
                    category_col.is_(None) |
                    ~category_col.in_(list(smart_hidden))
                )
    if auto_flag_filter is not None:
        query = query.filter(BankTransaction.auto_flag == auto_flag_filter)
    if teller_category is not None:
        query = query.filter(
            BankTransaction.details["category"].astext == teller_category
        )
    return query


@router.get("/transactions/count")
async def count_transactions(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    is_hsa_eligible: Optional[bool] = Query(None),
    include_potential_hsa: bool = Query(False),
    family_member_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    reimbursement_status: Optional[str] = Query(None),
    has_documents: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    show_hidden: bool = Query(False),
    show_all_categories: bool = Query(False),
    auto_flag_filter: Optional[str] = Query(None, alias="auto_flag"),
    teller_category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> int:
    """Return the total count of transactions matching the given filters."""
    readable_owner_ids = get_readable_owner_ids(current_user, db, resource="transactions")
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id.in_(readable_owner_ids), BankConnection.is_active == True)
        .subquery()
    )
    return _build_transaction_query(
        db, user_connection_ids,
        current_user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        is_hsa_eligible=is_hsa_eligible,
        include_potential_hsa=include_potential_hsa,
        family_member_id=family_member_id,
        status=status,
        reimbursement_status=reimbursement_status,
        has_documents=has_documents,
        search=search,
        show_hidden=show_hidden,
        show_all_categories=show_all_categories,
        auto_flag_filter=auto_flag_filter,
        teller_category=teller_category,
    ).count()


@router.get("/transactions", response_model=list[BankTransactionResponse])
async def list_all_transactions(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    is_hsa_eligible: Optional[bool] = Query(None, description="Filter by HSA eligibility (omit = all, true = HSA only, false = non-HSA only)"),
    include_potential_hsa: bool = Query(False, description="When is_hsa_eligible=true, also include potential_hsa auto-flagged transactions"),
    family_member_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None, description="posted or pending"),
    reimbursement_status: Optional[str] = Query(None, description="Filter by reimbursement status (e.g. 'reimbursed', 'null' for unset)"),
    has_documents: Optional[bool] = Query(None, description="Filter by documentation status (true = has receipts, false = missing receipts)"),
    search: Optional[str] = Query(None, description="Case-insensitive substring match on description"),
    show_hidden: bool = Query(False, description="Include transactions flagged as hidden (default: excluded)"),
    show_all_categories: bool = Query(False, description="Disable smart category filter — show non-HSA categories like food, gas, entertainment"),
    auto_flag_filter: Optional[str] = Query(None, alias="auto_flag", description="Filter to transactions with this auto_flag value"),
    teller_category: Optional[str] = Query(None, description="Filter by Teller-provided category (e.g. 'health', 'food_and_drink')"),
    limit: int = Query(50, le=2000),
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
    query = _build_transaction_query(
        db, user_connection_ids,
        current_user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        is_hsa_eligible=is_hsa_eligible,
        include_potential_hsa=include_potential_hsa,
        family_member_id=family_member_id,
        status=status,
        reimbursement_status=reimbursement_status,
        has_documents=has_documents,
        search=search,
        show_hidden=show_hidden,
        show_all_categories=show_all_categories,
        auto_flag_filter=auto_flag_filter,
        teller_category=teller_category,
    )

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

    # Build eligibility period lookup for warning badges
    household = _get_user_household(current_user.id, db)
    member_periods: dict = _load_member_periods(household.id, db) if household else {}

    return [
        _txn_to_response(
            t,
            counts.get(t.id, 0),
            _owner_name(t),
            eligibility_warning=not _is_eligible(member_periods, t.family_member_id, t.transaction_date),
        )
        for t in txns
    ]


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
    household = _get_user_household(current_user.id, db)
    member_periods: dict = _load_member_periods(household.id, db) if household else {}
    return _txn_to_response(
        txn,
        doc_count,
        eligibility_warning=not _is_eligible(member_periods, txn.family_member_id, txn.transaction_date),
    )


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

    # Auto-determine from_date when not explicitly provided
    if from_date is None:
        household = _get_user_household(current_user.id, db)
        hsa_start = _earliest_hsa_start(household.id, db) if household else None
        oldest_in_db = (
            db.query(func.min(BankTransaction.transaction_date))
            .filter(BankTransaction.connection_id == connection.id)
            .scalar()
        )
        if hsa_start:
            history_complete = oldest_in_db is not None and oldest_in_db <= hsa_start
            if history_complete:
                lookback = (
                    connection.last_synced_at.date() - timedelta(days=7)
                    if connection.last_synced_at else hsa_start
                )
                from_date = max(lookback, hsa_start)
            else:
                from_date = hsa_start
        elif connection.last_synced_at:
            from_date = connection.last_synced_at.date() - timedelta(days=7)
        # else: first-ever sync, no HSA periods — fetch whatever Teller returns

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

    potential_hsa_count = sum(1 for t in new_txns if t.auto_flag == "potential_hsa")
    return SyncResult(added=added, skipped=skipped, account_id=str(account_id), potential_hsa_count=potential_hsa_count)


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
