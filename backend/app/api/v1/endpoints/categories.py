"""Expense category endpoints"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.category import ExpenseCategory
from app.models.family import FamilyMember
from app.models.user import User
from app.schemas.transaction import CategoryCreate, CategoryResponse
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


@router.get("/", response_model=List[CategoryResponse])
async def list_categories(
    include_system: bool = Query(True, description="Include system categories"),
    include_custom: bool = Query(True, description="Include family custom categories"),
    hsa_eligible_only: bool = Query(False, description="Show only HSA-eligible categories"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all categories (system + family custom categories)

    Returns:
    - System categories (IRS-qualified HSA expenses)
    - Family-specific custom categories
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Build query
    query = db.query(ExpenseCategory)

    # Filter by system and/or custom
    if include_system and not include_custom:
        query = query.filter(ExpenseCategory.is_system_category == True)
    elif include_custom and not include_system:
        query = query.filter(
            ExpenseCategory.family_id == family_id,
            ExpenseCategory.is_system_category == False
        )
    elif include_system and include_custom:
        # Include both: system categories OR family custom categories
        query = query.filter(
            (ExpenseCategory.is_system_category == True) |
            (ExpenseCategory.family_id == family_id)
        )
    else:
        # Neither selected - return empty
        return []

    # Filter by HSA eligibility if requested
    if hsa_eligible_only:
        query = query.filter(ExpenseCategory.is_hsa_eligible == True)

    # Order by name
    categories = query.order_by(ExpenseCategory.name).all()

    return categories


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a custom category for the user's family

    Allows families to create their own custom expense categories
    in addition to the system categories.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Verify parent category exists if provided
    if category.parent_category_id:
        parent = db.query(ExpenseCategory).filter(
            ExpenseCategory.id == category.parent_category_id
        ).first()

        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent category not found"
            )

        # Verify parent is either system or belongs to family
        if parent.family_id is not None and parent.family_id != family_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to the parent category"
            )

    # Create custom category
    db_category = ExpenseCategory(
        family_id=family_id,
        name=category.name,
        description=category.description,
        is_hsa_eligible=category.is_hsa_eligible,
        parent_category_id=category.parent_category_id,
        is_system_category=False,  # Custom category
    )

    db.add(db_category)
    db.commit()
    db.refresh(db_category)

    return db_category


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific category by ID

    Returns category if it's a system category or belongs to user's family.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query category
    category = db.query(ExpenseCategory).filter(
        ExpenseCategory.id == category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    # Verify access: either system category or belongs to user's family
    if category.family_id is not None and category.family_id != family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this category"
        )

    return category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    category_update: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a custom category

    Note: System categories cannot be updated.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query category
    db_category = db.query(ExpenseCategory).filter(
        ExpenseCategory.id == category_id
    ).first()

    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    # Verify it's not a system category
    if db_category.is_system_category:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System categories cannot be modified"
        )

    # Verify it belongs to user's family
    if db_category.family_id != family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this category"
        )

    # Update fields
    db_category.name = category_update.name
    db_category.description = category_update.description
    db_category.is_hsa_eligible = category_update.is_hsa_eligible
    db_category.parent_category_id = category_update.parent_category_id

    db.commit()
    db.refresh(db_category)

    return db_category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a custom category

    Note: System categories cannot be deleted.
    Categories in use by transactions cannot be deleted.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query category
    db_category = db.query(ExpenseCategory).filter(
        ExpenseCategory.id == category_id
    ).first()

    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    # Verify it's not a system category
    if db_category.is_system_category:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System categories cannot be deleted"
        )

    # Verify it belongs to user's family
    if db_category.family_id != family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this category"
        )

    # Check if category is in use (has transactions)
    # Note: This will fail if RESTRICT constraint is set on foreign key
    # We could also check manually:
    # if db_category.transactions:
    #     raise HTTPException(...)

    # Delete category
    db.delete(db_category)
    db.commit()

    return None
