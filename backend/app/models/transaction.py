"""Transaction and Receipt models for expense tracking"""

import uuid
import enum
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Numeric, Integer, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class PaymentMethod(str, enum.Enum):
    """How the expense was paid"""
    HSA_CARD = "hsa_card"
    PERSONAL = "personal"
    OTHER = "other"


class ReimbursementStatus(str, enum.Enum):
    """Status of reimbursement from HSA"""
    NOT_NEEDED = "not_needed"  # Paid with HSA card
    PENDING = "pending"  # Waiting for reimbursement
    REIMBURSED = "reimbursed"  # Already reimbursed
    NOT_SEEKING = "not_seeking"  # Won't seek reimbursement


class Transaction(Base):
    """HSA expense transaction"""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    family_member_id = Column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    hsa_account_id = Column(UUID(as_uuid=True), ForeignKey("hsa_accounts.id", ondelete="SET NULL"), nullable=True, index=True)

    transaction_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    merchant_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    payment_method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.PERSONAL)
    reimbursement_status = Column(Enum(ReimbursementStatus), nullable=False, default=ReimbursementStatus.PENDING)
    reimbursed_date = Column(Date, nullable=True)

    tax_year = Column(Integer, nullable=False, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    family = relationship("Family", back_populates="transactions")
    family_member = relationship("FamilyMember", back_populates="transactions")
    category = relationship("ExpenseCategory", back_populates="transactions")
    created_by_user = relationship("User", backref="created_transactions")
    receipts = relationship("Receipt", back_populates="transaction", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount}, date={self.transaction_date}, merchant={self.merchant_name})>"


class Receipt(Base):
    """Receipt file stored in S3"""
    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True)

    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    mime_type = Column(String(100), nullable=False)

    s3_key = Column(String(512), nullable=False, unique=True)
    s3_bucket = Column(String(255), nullable=False)
    thumbnail_s3_key = Column(String(512), nullable=True)  # Optional thumbnail

    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    transaction = relationship("Transaction", back_populates="receipts")
    uploaded_by_user = relationship("User", backref="uploaded_receipts")

    def __repr__(self):
        return f"<Receipt(id={self.id}, file_name={self.file_name}, transaction_id={self.transaction_id})>"
