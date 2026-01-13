"""Transaction and Receipt Pydantic schemas"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, validator

from app.models.transaction import PaymentMethod, ReimbursementStatus


# Transaction Schemas

class TransactionBase(BaseModel):
    """Base transaction schema"""
    family_member_id: UUID
    category_id: UUID
    transaction_date: date
    amount: Decimal = Field(gt=0, decimal_places=2)
    merchant_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    payment_method: PaymentMethod = PaymentMethod.PERSONAL
    reimbursement_status: ReimbursementStatus = ReimbursementStatus.PENDING
    reimbursed_date: Optional[date] = None
    tax_year: Optional[int] = None
    hsa_account_id: Optional[UUID] = None

    @validator("tax_year", pre=True, always=True)
    def set_tax_year(cls, v, values):
        """Auto-set tax year from transaction date if not provided"""
        if v is None and "transaction_date" in values:
            return values["transaction_date"].year
        return v

    @validator("reimbursed_date")
    def validate_reimbursed_date(cls, v, values):
        """Ensure reimbursed_date is set when status is reimbursed"""
        if values.get("reimbursement_status") == ReimbursementStatus.REIMBURSED and v is None:
            raise ValueError("reimbursed_date is required when status is reimbursed")
        return v


class TransactionCreate(TransactionBase):
    """Schema for creating a transaction"""
    pass


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction (all fields optional)"""
    family_member_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    transaction_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    merchant_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    reimbursement_status: Optional[ReimbursementStatus] = None
    reimbursed_date: Optional[date] = None
    tax_year: Optional[int] = None
    hsa_account_id: Optional[UUID] = None


class TransactionResponse(TransactionBase):
    """Schema for transaction response"""
    id: UUID
    family_id: UUID
    created_by_user_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Receipt Schemas

class ReceiptBase(BaseModel):
    """Base receipt schema"""
    file_name: str = Field(..., max_length=255)
    file_size: int = Field(..., gt=0)
    mime_type: str = Field(..., max_length=100)


class ReceiptCreate(ReceiptBase):
    """Schema for creating a receipt"""
    s3_key: str = Field(..., max_length=512)
    s3_bucket: str = Field(..., max_length=255)
    thumbnail_s3_key: Optional[str] = Field(None, max_length=512)


class ReceiptResponse(ReceiptBase):
    """Schema for receipt response"""
    id: UUID
    transaction_id: UUID
    s3_key: str
    s3_bucket: str
    thumbnail_s3_key: Optional[str]
    upload_date: datetime
    uploaded_by_user_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


# Category Schemas

class CategoryBase(BaseModel):
    """Base category schema"""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_hsa_eligible: bool = True
    parent_category_id: Optional[UUID] = None


class CategoryCreate(CategoryBase):
    """Schema for creating a custom category"""
    pass


class CategoryResponse(CategoryBase):
    """Schema for category response"""
    id: UUID
    family_id: Optional[UUID]  # None for system categories
    is_system_category: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Query/Filter Schemas

class TransactionFilters(BaseModel):
    """Filters for transaction list"""
    family_member_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    payment_method: Optional[PaymentMethod] = None
    reimbursement_status: Optional[ReimbursementStatus] = None
    tax_year: Optional[int] = None
    search: Optional[str] = None  # Search merchant or description
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class TransactionListResponse(BaseModel):
    """Response for transaction list with pagination"""
    transactions: list[TransactionResponse]
    total: int
    skip: int
    limit: int
