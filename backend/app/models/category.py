"""Expense category models for HSA-eligible expense tracking"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ExpenseCategory(Base):
    """Expense categories (system-defined and custom)"""
    __tablename__ = "expense_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=True, index=True)  # Null for system categories
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_hsa_eligible = Column(Boolean, default=True, nullable=False)
    parent_category_id = Column(UUID(as_uuid=True), ForeignKey("expense_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    is_system_category = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    family = relationship("Family", back_populates="categories")
    parent_category = relationship("ExpenseCategory", remote_side=[id], backref="subcategories")
    transactions = relationship("Transaction", back_populates="category")

    def __repr__(self):
        return f"<ExpenseCategory(id={self.id}, name={self.name}, is_hsa_eligible={self.is_hsa_eligible})>"
