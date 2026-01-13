"""HSA Account models for account management"""

import uuid
import enum
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Numeric, Integer, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ContributionLimitType(str, enum.Enum):
    """HSA contribution limit type"""
    INDIVIDUAL = "individual"
    FAMILY = "family"


class ContributionType(str, enum.Enum):
    """Type of HSA contribution"""
    EMPLOYEE = "employee"
    EMPLOYER = "employer"
    OTHER = "other"


class HSAAccount(Base):
    """HSA account for tracking balance and contributions"""
    __tablename__ = "hsa_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    account_holder_id = Column(UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    current_balance = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    contribution_limit_type = Column(Enum(ContributionLimitType), nullable=False, default=ContributionLimitType.INDIVIDUAL)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    family = relationship("Family", backref="hsa_accounts")
    account_holder = relationship("FamilyMember", backref="held_hsa_accounts")
    contributions = relationship("HSAContribution", back_populates="hsa_account", cascade="all, delete-orphan")
    transactions = relationship("Transaction", backref="hsa_account")

    def __repr__(self):
        return f"<HSAAccount(id={self.id}, name={self.name}, balance={self.current_balance})>"


class HSAContribution(Base):
    """HSA contribution tracking"""
    __tablename__ = "hsa_contributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hsa_account_id = Column(UUID(as_uuid=True), ForeignKey("hsa_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    amount = Column(Numeric(10, 2), nullable=False)
    contribution_date = Column(Date, nullable=False, index=True)
    contribution_type = Column(Enum(ContributionType), nullable=False, default=ContributionType.EMPLOYEE)
    tax_year = Column(Integer, nullable=False, index=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    hsa_account = relationship("HSAAccount", back_populates="contributions")

    def __repr__(self):
        return f"<HSAContribution(id={self.id}, amount={self.amount}, date={self.contribution_date})>"
