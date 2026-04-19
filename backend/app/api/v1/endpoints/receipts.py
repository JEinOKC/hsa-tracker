"""Retailer import endpoints — CVS pharmacy CSV and generic receipt line items.

Endpoints:
  POST   /bank/imports/cvs-pharmacy                                - import CVS Financial Summary CSV
  GET    /bank/pharmacy-fills                                      - list fills (all or unmatched only)
  GET    /bank/transactions/{txn_id}/pharmacy-fills                - fills linked to a transaction
  POST   /bank/pharmacy-fills/{fill_id}/link                      - manually link a fill to a transaction
  DELETE /bank/pharmacy-fills/{fill_id}/link                      - unlink a fill from a transaction
  GET    /bank/imports/line-items-template.csv                     - download generic CSV template
  POST   /bank/transactions/{txn_id}/line-items/import-csv        - import generic line item CSV
  GET    /bank/transactions/{txn_id}/line-items                   - list line items for a transaction
  POST   /bank/transactions/{txn_id}/line-items                   - create a line item manually
  PATCH  /bank/transactions/{txn_id}/line-items/{item_id}         - update a line item
  DELETE /bank/transactions/{txn_id}/line-items/{item_id}         - delete a line item
"""

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.bank import (
    BankConnection,
    BankTransaction,
    PharmacyFill,
    PharmacyImportBatch,
    ReceiptLineItem,
)
from app.models.user import User
from app.services.cvs_parser import CvsParseError, parse_cvs_financial_summary
from app.utils.access import get_readable_owner_ids

router = APIRouter()

_MAX_LINE_ITEM_ROWS = 200


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PharmacyFillResponse(BaseModel):
    id: UUID
    drug_name: str
    rx_number: Optional[str]
    fill_date: date
    amount_paid: Decimal
    pharmacy: Optional[str]
    member_name: Optional[str]
    transaction_id: Optional[UUID]
    matched: bool

    class Config:
        from_attributes = True


class PharmacyImportResult(BaseModel):
    batch_id: UUID
    row_count: int
    matched: int
    unmatched: int
    fills: list[PharmacyFillResponse]


class LinkFillRequest(BaseModel):
    transaction_id: UUID


class LineItemResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    description: str
    amount: Decimal
    quantity: int
    is_hsa_eligible: Optional[bool]
    hsa_category: Optional[str]
    source: str

    class Config:
        from_attributes = True


class LineItemCreate(BaseModel):
    description: str
    amount: Decimal
    quantity: int = 1
    is_hsa_eligible: Optional[bool] = None
    hsa_category: Optional[str] = None


class LineItemUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    quantity: Optional[int] = None
    is_hsa_eligible: Optional[bool] = None
    hsa_category: Optional[str] = None


class LineItemImportResult(BaseModel):
    line_items: list[LineItemResponse]
    eligible_total: Optional[Decimal]
    item_count: int


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------


def _get_transaction_or_404(
    transaction_id: UUID,
    user: User,
    db: Session,
) -> BankTransaction:
    """Return the transaction if the user has read access, else raise 404."""
    readable_owner_ids = get_readable_owner_ids(user, db)
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id.in_(readable_owner_ids))
        .scalar_subquery()
    )
    txn = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.id == transaction_id,
            or_(
                BankTransaction.connection_id.in_(user_connection_ids),
                and_(
                    BankTransaction.connection_id == None,
                    BankTransaction.user_id.in_(readable_owner_ids),
                ),
            ),
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return txn


def _get_fill_or_404(fill_id: UUID, user: User, db: Session) -> PharmacyFill:
    fill = db.query(PharmacyFill).filter(PharmacyFill.id == fill_id).first()
    if not fill:
        raise HTTPException(status_code=404, detail="Pharmacy fill not found.")
    readable_owner_ids = get_readable_owner_ids(user, db)
    if fill.user_id not in readable_owner_ids:
        raise HTTPException(status_code=404, detail="Pharmacy fill not found.")
    return fill


def _get_line_item_or_404(item_id: UUID, transaction_id: UUID, db: Session) -> ReceiptLineItem:
    item = (
        db.query(ReceiptLineItem)
        .filter(
            ReceiptLineItem.id == item_id,
            ReceiptLineItem.transaction_id == transaction_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found.")
    return item


# ---------------------------------------------------------------------------
# Eligible amount helpers
# ---------------------------------------------------------------------------


def _recompute_eligible_amount(txn: BankTransaction, db: Session) -> None:
    """Recompute and save transaction.eligible_amount from its line items.

    Sets eligible_amount to the sum of items where is_hsa_eligible is True.
    Sets to None if no eligible items exist.
    Only updates if eligible_amount was derived from line items (not set by
    the user directly before any line items existed, but since we have no
    'source' flag on eligible_amount we always recompute when line items exist).
    """
    items = (
        db.query(ReceiptLineItem)
        .filter(ReceiptLineItem.transaction_id == txn.id)
        .all()
    )
    eligible_sum = sum(
        item.amount for item in items if item.is_hsa_eligible is True
    )
    txn.eligible_amount = eligible_sum if eligible_sum > 0 else None
    db.flush()


# ---------------------------------------------------------------------------
# CVS pharmacy matching logic
# ---------------------------------------------------------------------------


def _match_fills_to_transactions(
    fills,
    user: User,
    db: Session,
) -> dict:
    """Try to match each ParsedFill to an existing bank transaction.

    Returns a dict mapping fill index → BankTransaction (or None if unmatched).
    Each transaction is matched at most once per batch.
    """
    from app.services.cvs_parser import ParsedFill

    readable_owner_ids = get_readable_owner_ids(user, db)

    # Build a candidate pool: all CVS-like transactions in the date range of the fills
    if not fills:
        return {}

    min_date = min(f.fill_date for f in fills)
    max_date = max(f.fill_date for f in fills)

    from datetime import timedelta

    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id.in_(readable_owner_ids))
        .scalar_subquery()
    )

    candidates = (
        db.query(BankTransaction)
        .filter(
            or_(
                BankTransaction.connection_id.in_(user_connection_ids),
                and_(
                    BankTransaction.connection_id == None,
                    BankTransaction.user_id.in_(readable_owner_ids),
                ),
            ),
            BankTransaction.transaction_date >= min_date - timedelta(days=3),
            BankTransaction.transaction_date <= max_date + timedelta(days=3),
        )
        .all()
    )

    matched_txn_ids: set = set()
    result: dict = {}

    for idx, fill in enumerate(fills):
        best_match = None
        best_date_diff = None

        for txn in candidates:
            if txn.id in matched_txn_ids:
                continue

            # Date within ±3 days
            date_diff = abs((txn.transaction_date - fill.fill_date).days)
            if date_diff > 3:
                continue

            # Amount within 2% (amount is stored as negative for debits)
            txn_abs = abs(txn.amount)
            if txn_abs == 0:
                continue
            pct_diff = abs(txn_abs - fill.amount_paid) / txn_abs
            if pct_diff > 0.02:
                continue

            # Prefer closest date match
            if best_date_diff is None or date_diff < best_date_diff:
                best_match = txn
                best_date_diff = date_diff

        if best_match:
            result[idx] = best_match
            matched_txn_ids.add(best_match.id)
        else:
            result[idx] = None

    return result


def _apply_hsa_annotation_from_fill(txn: BankTransaction, fill, db: Session) -> None:
    """Mark a transaction as a prescription when a pharmacy fill is linked."""
    txn.is_hsa_eligible = True
    txn.hsa_category = "prescription"
    if txn.eligible_amount is None:
        txn.eligible_amount = fill.amount_paid
    # Append drug name to notes
    drug_note = f"CVS: {fill.drug_name}"
    if txn.notes:
        if drug_note not in txn.notes:
            txn.notes = txn.notes + f"\n{drug_note}"
    else:
        txn.notes = drug_note
    db.flush()


# ---------------------------------------------------------------------------
# Endpoints — CVS pharmacy import
# ---------------------------------------------------------------------------


@router.post("/imports/cvs-pharmacy", response_model=PharmacyImportResult, status_code=201)
async def import_cvs_pharmacy(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a CVS Financial Summary CSV and match fills to bank transactions.

    Download the CSV from cvs.com → Prescriptions → Financial Summary → Download.
    Each prescription fill row is matched to an existing bank transaction by
    date (±3 days) and amount (±2%). Matched transactions are automatically
    marked as HSA-eligible prescriptions.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    try:
        parsed_fills = parse_cvs_financial_summary(content)
    except CvsParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Match fills to transactions
    match_map = _match_fills_to_transactions(parsed_fills, current_user, db)

    matched_count = sum(1 for v in match_map.values() if v is not None)
    unmatched_count = len(parsed_fills) - matched_count

    # Create batch record
    batch = PharmacyImportBatch(
        user_id=current_user.id,
        filename=file.filename or "financial-summary.csv",
        source="cvs_financial_summary",
        row_count=len(parsed_fills),
        matched=matched_count,
        unmatched=unmatched_count,
    )
    db.add(batch)
    db.flush()

    # Create fill records and apply annotations
    fill_responses = []
    for idx, parsed in enumerate(parsed_fills):
        matched_txn = match_map.get(idx)

        fill = PharmacyFill(
            user_id=current_user.id,
            import_batch_id=batch.id,
            transaction_id=matched_txn.id if matched_txn else None,
            member_name=parsed.member_name,
            drug_name=parsed.drug_name,
            rx_number=parsed.rx_number,
            fill_date=parsed.fill_date,
            amount_paid=parsed.amount_paid,
            pharmacy=parsed.pharmacy,
            source="cvs_financial_summary",
        )
        db.add(fill)
        db.flush()

        if matched_txn:
            _apply_hsa_annotation_from_fill(matched_txn, fill, db)

        fill_responses.append(PharmacyFillResponse(
            id=fill.id,
            drug_name=fill.drug_name,
            rx_number=fill.rx_number,
            fill_date=fill.fill_date,
            amount_paid=fill.amount_paid,
            pharmacy=fill.pharmacy,
            member_name=fill.member_name,
            transaction_id=fill.transaction_id,
            matched=matched_txn is not None,
        ))

    db.commit()

    return PharmacyImportResult(
        batch_id=batch.id,
        row_count=len(parsed_fills),
        matched=matched_count,
        unmatched=unmatched_count,
        fills=fill_responses,
    )


@router.get("/pharmacy-fills", response_model=list[PharmacyFillResponse])
async def list_pharmacy_fills(
    unmatched: bool = Query(False, description="Only return fills with no linked transaction"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List pharmacy fills for the current user."""
    readable_owner_ids = get_readable_owner_ids(current_user, db)
    query = db.query(PharmacyFill).filter(PharmacyFill.user_id.in_(readable_owner_ids))
    if unmatched:
        query = query.filter(PharmacyFill.transaction_id == None)
    fills = query.order_by(PharmacyFill.fill_date.desc()).all()
    return [
        PharmacyFillResponse(
            id=f.id,
            drug_name=f.drug_name,
            rx_number=f.rx_number,
            fill_date=f.fill_date,
            amount_paid=f.amount_paid,
            pharmacy=f.pharmacy,
            member_name=f.member_name,
            transaction_id=f.transaction_id,
            matched=f.transaction_id is not None,
        )
        for f in fills
    ]


@router.get(
    "/transactions/{transaction_id}/pharmacy-fills",
    response_model=list[PharmacyFillResponse],
)
async def list_transaction_fills(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List pharmacy fills linked to a specific transaction."""
    _get_transaction_or_404(transaction_id, current_user, db)
    fills = (
        db.query(PharmacyFill)
        .filter(PharmacyFill.transaction_id == transaction_id)
        .order_by(PharmacyFill.fill_date.desc())
        .all()
    )
    return [
        PharmacyFillResponse(
            id=f.id,
            drug_name=f.drug_name,
            rx_number=f.rx_number,
            fill_date=f.fill_date,
            amount_paid=f.amount_paid,
            pharmacy=f.pharmacy,
            member_name=f.member_name,
            transaction_id=f.transaction_id,
            matched=True,
        )
        for f in fills
    ]


@router.post("/pharmacy-fills/{fill_id}/link", status_code=200)
async def link_fill_to_transaction(
    fill_id: UUID,
    payload: LinkFillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually link an unmatched pharmacy fill to a bank transaction."""
    fill = _get_fill_or_404(fill_id, current_user, db)
    txn = _get_transaction_or_404(payload.transaction_id, current_user, db)

    fill.transaction_id = txn.id
    _apply_hsa_annotation_from_fill(txn, fill, db)
    db.commit()
    return {"status": "linked", "transaction_id": str(txn.id)}


@router.delete("/pharmacy-fills/{fill_id}/link", status_code=204)
async def unlink_fill_from_transaction(
    fill_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the link between a fill and its bank transaction.

    The transaction's HSA annotations are left untouched — adjust them
    manually if needed.
    """
    fill = _get_fill_or_404(fill_id, current_user, db)
    fill.transaction_id = None
    db.commit()


# ---------------------------------------------------------------------------
# Endpoints — generic line items
# ---------------------------------------------------------------------------


@router.get("/imports/line-items-template.csv", response_class=PlainTextResponse)
async def download_line_items_template():
    """Download a CSV template for generic receipt line item import."""
    template = (
        "description,amount,quantity,is_hsa_eligible,hsa_category\n"
        "BANDAGE ASSORTED,4.99,1,true,medical\n"
        "HEAD&SHOULDERS SHAMPOO,6.99,1,false,\n"
        "IBUPROFEN 200MG,8.49,1,true,otc\n"
    )
    return PlainTextResponse(
        content=template,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=line-items-template.csv"},
    )


@router.post(
    "/transactions/{transaction_id}/line-items/import-csv",
    response_model=LineItemImportResult,
    status_code=201,
)
async def import_line_items_csv(
    transaction_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a CSV of line items for a transaction.

    Required columns: description, amount
    Optional columns: quantity, is_hsa_eligible (true/false), hsa_category
    Maximum 200 rows.
    """
    txn = _get_transaction_or_404(transaction_id, current_user, db)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    # Normalise header names (strip whitespace, lowercase)
    reader.fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

    if "description" not in (reader.fieldnames or []):
        raise HTTPException(status_code=422, detail="Required column 'description' not found in CSV.")
    if "amount" not in (reader.fieldnames or []):
        raise HTTPException(status_code=422, detail="Required column 'amount' not found in CSV.")

    rows = list(reader)
    if len(rows) > _MAX_LINE_ITEM_ROWS:
        raise HTTPException(
            status_code=422,
            detail=f"CSV has {len(rows)} rows; maximum is {_MAX_LINE_ITEM_ROWS}.",
        )

    items = []
    for i, row in enumerate(rows, start=1):
        description = (row.get("description") or "").strip()
        if not description:
            raise HTTPException(status_code=422, detail=f"Row {i}: 'description' is empty.")

        raw_amount = (row.get("amount") or "").strip().lstrip("$").replace(",", "")
        try:
            amount = Decimal(raw_amount)
        except InvalidOperation:
            raise HTTPException(status_code=422, detail=f"Row {i}: invalid amount '{row.get('amount')}'.")

        quantity = 1
        raw_qty = (row.get("quantity") or "").strip()
        if raw_qty:
            try:
                quantity = int(raw_qty)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Row {i}: invalid quantity '{raw_qty}'.")

        raw_hsa = (row.get("is_hsa_eligible") or "").strip().lower()
        is_hsa_eligible = None
        if raw_hsa in ("true", "yes", "1"):
            is_hsa_eligible = True
        elif raw_hsa in ("false", "no", "0"):
            is_hsa_eligible = False

        hsa_category = (row.get("hsa_category") or "").strip() or None

        item = ReceiptLineItem(
            transaction_id=transaction_id,
            user_id=current_user.id,
            description=description,
            amount=amount,
            quantity=quantity,
            is_hsa_eligible=is_hsa_eligible,
            hsa_category=hsa_category,
            source="csv_generic",
        )
        db.add(item)
        items.append(item)

    db.flush()
    _recompute_eligible_amount(txn, db)
    db.commit()
    for item in items:
        db.refresh(item)

    eligible_total = txn.eligible_amount

    return LineItemImportResult(
        line_items=[LineItemResponse.model_validate(item) for item in items],
        eligible_total=eligible_total,
        item_count=len(items),
    )


@router.get(
    "/transactions/{transaction_id}/line-items",
    response_model=list[LineItemResponse],
)
async def list_line_items(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all line items for a transaction."""
    _get_transaction_or_404(transaction_id, current_user, db)
    items = (
        db.query(ReceiptLineItem)
        .filter(ReceiptLineItem.transaction_id == transaction_id)
        .order_by(ReceiptLineItem.created_at.asc())
        .all()
    )
    return [LineItemResponse.model_validate(item) for item in items]


@router.post(
    "/transactions/{transaction_id}/line-items",
    response_model=LineItemResponse,
    status_code=201,
)
async def create_line_item(
    transaction_id: UUID,
    payload: LineItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually create a line item for a transaction."""
    txn = _get_transaction_or_404(transaction_id, current_user, db)
    item = ReceiptLineItem(
        transaction_id=transaction_id,
        user_id=current_user.id,
        description=payload.description,
        amount=payload.amount,
        quantity=payload.quantity,
        is_hsa_eligible=payload.is_hsa_eligible,
        hsa_category=payload.hsa_category,
        source="manual",
    )
    db.add(item)
    db.flush()
    _recompute_eligible_amount(txn, db)
    db.commit()
    db.refresh(item)
    return LineItemResponse.model_validate(item)


@router.patch(
    "/transactions/{transaction_id}/line-items/{item_id}",
    response_model=LineItemResponse,
)
async def update_line_item(
    transaction_id: UUID,
    item_id: UUID,
    payload: LineItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a line item and recompute the transaction's eligible_amount."""
    txn = _get_transaction_or_404(transaction_id, current_user, db)
    item = _get_line_item_or_404(item_id, transaction_id, db)

    if payload.description is not None:
        item.description = payload.description
    if payload.amount is not None:
        item.amount = payload.amount
    if payload.quantity is not None:
        item.quantity = payload.quantity
    if payload.is_hsa_eligible is not None or "is_hsa_eligible" in payload.model_fields_set:
        item.is_hsa_eligible = payload.is_hsa_eligible
    if payload.hsa_category is not None or "hsa_category" in payload.model_fields_set:
        item.hsa_category = payload.hsa_category

    db.flush()
    _recompute_eligible_amount(txn, db)
    db.commit()
    db.refresh(item)
    return LineItemResponse.model_validate(item)


@router.delete(
    "/transactions/{transaction_id}/line-items/{item_id}",
    status_code=204,
)
async def delete_line_item(
    transaction_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a line item and recompute the transaction's eligible_amount."""
    txn = _get_transaction_or_404(transaction_id, current_user, db)
    item = _get_line_item_or_404(item_id, transaction_id, db)
    db.delete(item)
    db.flush()
    _recompute_eligible_amount(txn, db)
    db.commit()
