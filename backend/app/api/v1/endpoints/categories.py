"""Expense category endpoints"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class CategoryBase(BaseModel):
    """Base category schema"""
    name: str
    description: Optional[str] = None
    is_hsa_eligible: bool = True
    parent_category_id: Optional[str] = None


class CategoryCreate(CategoryBase):
    """Schema for creating a custom category"""
    pass


class Category(CategoryBase):
    """Category response schema"""
    id: str
    family_id: Optional[str]  # None for system categories
    is_system_category: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[Category])
async def list_categories(
    family_id: Optional[str] = None,
    include_system: bool = True,
):
    """
    List all categories (system + family custom categories).

    This is a placeholder endpoint. Full implementation will include:
    - Get system categories (predefined HSA-eligible categories)
    - Get family-specific custom categories
    - Return combined list

    System categories include:
    - Medical care and services
    - Dental care
    - Vision care
    - Prescription medications
    - Over-the-counter medications
    - Medical equipment and supplies
    - Mental health services
    - Preventive care
    - COVID-19 testing and PPE
    - Menstrual care products
    - Direct Primary Care (DPC) fees
    """
    # Placeholder system categories
    system_categories = [
        {
            "id": "cat_medical",
            "name": "Medical Care",
            "description": "General medical care and services",
            "is_hsa_eligible": True,
            "parent_category_id": None,
            "family_id": None,
            "is_system_category": True,
            "created_at": datetime.now(),
        },
        {
            "id": "cat_dental",
            "name": "Dental Care",
            "description": "Dental services and treatments",
            "is_hsa_eligible": True,
            "parent_category_id": None,
            "family_id": None,
            "is_system_category": True,
            "created_at": datetime.now(),
        },
        {
            "id": "cat_vision",
            "name": "Vision Care",
            "description": "Eye exams, glasses, contacts",
            "is_hsa_eligible": True,
            "parent_category_id": None,
            "family_id": None,
            "is_system_category": True,
            "created_at": datetime.now(),
        },
        {
            "id": "cat_prescription",
            "name": "Prescription Medications",
            "description": "Prescription drugs and medications",
            "is_hsa_eligible": True,
            "parent_category_id": None,
            "family_id": None,
            "is_system_category": True,
            "created_at": datetime.now(),
        },
        {
            "id": "cat_otc",
            "name": "Over-the-Counter",
            "description": "OTC medications and supplies",
            "is_hsa_eligible": True,
            "parent_category_id": None,
            "family_id": None,
            "is_system_category": True,
            "created_at": datetime.now(),
        },
    ]

    return system_categories


@router.post("/", response_model=Category, status_code=201)
async def create_category(category: CategoryCreate):
    """
    Create a custom category for a family.

    This is a placeholder endpoint. Full implementation will include:
    - Validate user has access to family
    - Create custom category
    - Return created category
    """
    raise HTTPException(
        status_code=501,
        detail="Create custom category endpoint not yet implemented"
    )


@router.get("/{category_id}", response_model=Category)
async def get_category(category_id: str):
    """
    Get a specific category by ID.

    This is a placeholder endpoint. Full implementation will include:
    - Query category from database
    - Verify access if family-specific
    - Return category details
    """
    raise HTTPException(
        status_code=404,
        detail=f"Category {category_id} not found or not yet implemented"
    )


@router.put("/{category_id}", response_model=Category)
async def update_category(category_id: str, category: CategoryCreate):
    """
    Update a custom category.

    Note: System categories cannot be updated.

    This is a placeholder endpoint. Full implementation will include:
    - Verify category is not a system category
    - Verify user has access to family
    - Update category
    - Return updated category
    """
    raise HTTPException(
        status_code=501,
        detail="Update category endpoint not yet implemented"
    )


@router.delete("/{category_id}", status_code=204)
async def delete_category(category_id: str):
    """
    Delete a custom category.

    Note: System categories cannot be deleted.

    This is a placeholder endpoint. Full implementation will include:
    - Verify category is not a system category
    - Verify user has access to family
    - Check if category is in use
    - Delete category or mark as inactive
    - Return success
    """
    raise HTTPException(
        status_code=501,
        detail="Delete category endpoint not yet implemented"
    )
