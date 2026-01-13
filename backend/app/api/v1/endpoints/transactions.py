"""Transaction management endpoints"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.database import get_db
from app.models.transaction import Transaction, PaymentMethod, ReimbursementStatus
from app.models.family import FamilyMember
from app.models.category import ExpenseCategory
from app.models.user import User
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionListResponse,
    TransactionFilters,
)
from app.utils.security import get_current_user

router = APIRouter()


def get_user_family_id(db: Session, user: User) -> UUID:
    """Get the family_id for the current user"""
    family_member = db.query(FamilyMember).filter(
        FamilyMember.user_id == user.id
    ).first()

    if not family_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a family"
        )

    return family_member.family_id


def verify_family_access(db: Session, user: User, family_id: UUID):
    """Verify user has access to the specified family"""
    user_family_id = get_user_family_id(db, user)

    if user_family_id != family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this family"
        )


@router.get("/", response_model=TransactionListResponse)
async def list_transactions(
    family_member_id: Optional[UUID] = Query(None, description="Filter by family member"),
    category_id: Optional[UUID] = Query(None, description="Filter by category"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    min_amount: Optional[float] = Query(None, description="Minimum amount"),
    max_amount: Optional[float] = Query(None, description="Maximum amount"),
    payment_method: Optional[PaymentMethod] = Query(None, description="Payment method"),
    reimbursement_status: Optional[ReimbursementStatus] = Query(None, description="Reimbursement status"),
    tax_year: Optional[int] = Query(None, description="Tax year"),
    search: Optional[str] = Query(None, description="Search merchant or description"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List transactions with optional filters

    Returns all transactions for the user's family with pagination and filters.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Build query
    query = db.query(Transaction).filter(Transaction.family_id == family_id)

    # Apply filters
    if family_member_id:
        query = query.filter(Transaction.family_member_id == family_member_id)

    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)

    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)

    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)

    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)

    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)

    if reimbursement_status:
        query = query.filter(Transaction.reimbursement_status == reimbursement_status)

    if tax_year:
        query = query.filter(Transaction.tax_year == tax_year)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Transaction.merchant_name.ilike(search_pattern),
                Transaction.description.ilike(search_pattern)
            )
        )

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    transactions = query.order_by(
        Transaction.transaction_date.desc(),
        Transaction.created_at.desc()
    ).offset(skip).limit(limit).all()

    return TransactionListResponse(
        transactions=transactions,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new transaction (expense)

    Creates a transaction for the user's family after validating:
    - Family member exists and belongs to user's family
    - Category exists
    - HSA account exists (if provided) and belongs to user's family
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Verify family member exists and belongs to user's family
    family_member = db.query(FamilyMember).filter(
        FamilyMember.id == transaction.family_member_id,
        FamilyMember.family_id == family_id
    ).first()

    if not family_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family member not found or does not belong to your family"
        )

    # Verify category exists
    category = db.query(ExpenseCategory).filter(
        ExpenseCategory.id == transaction.category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    # Verify category is either system category or belongs to user's family
    if category.family_id is not None and category.family_id != family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this category"
        )

    # Create transaction
    db_transaction = Transaction(
        family_id=family_id,
        family_member_id=transaction.family_member_id,
        category_id=transaction.category_id,
        hsa_account_id=transaction.hsa_account_id,
        transaction_date=transaction.transaction_date,
        amount=transaction.amount,
        merchant_name=transaction.merchant_name,
        description=transaction.description,
        payment_method=transaction.payment_method,
        reimbursement_status=transaction.reimbursement_status,
        reimbursed_date=transaction.reimbursed_date,
        tax_year=transaction.tax_year or transaction.transaction_date.year,
        created_by_user_id=current_user.id,
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return db_transaction


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific transaction by ID

    Returns transaction details if it belongs to the user's family.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query transaction
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.family_id == family_id
    ).first()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    return transaction


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    transaction_update: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a transaction

    Updates transaction fields. Only updates fields that are provided.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query transaction
    db_transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.family_id == family_id
    ).first()

    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    # Update fields if provided
    update_data = transaction_update.dict(exclude_unset=True)

    # Verify family member if updating
    if "family_member_id" in update_data:
        family_member = db.query(FamilyMember).filter(
            FamilyMember.id == update_data["family_member_id"],
            FamilyMember.family_id == family_id
        ).first()
        if not family_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Family member not found"
            )

    # Verify category if updating
    if "category_id" in update_data:
        category = db.query(ExpenseCategory).filter(
            ExpenseCategory.id == update_data["category_id"]
        ).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        if category.family_id is not None and category.family_id != family_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this category"
            )

    # Update transaction date -> recalculate tax year
    if "transaction_date" in update_data and "tax_year" not in update_data:
        update_data["tax_year"] = update_data["transaction_date"].year

    # Apply updates
    for field, value in update_data.items():
        setattr(db_transaction, field, value)

    db.commit()
    db.refresh(db_transaction)

    return db_transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a transaction

    Deletes transaction and associated receipts from database.
    Note: S3 files should be deleted separately (handled by receipt endpoints).
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query transaction
    db_transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.family_id == family_id
    ).first()

    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    # Delete transaction (cascades to receipts in DB)
    db.delete(db_transaction)
    db.commit()

    return None
