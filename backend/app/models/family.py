"""Family and Family Member models for multi-tenant support"""

import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Date, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class FamilyMemberRelationship(str, enum.Enum):
    """Relationship of family member to account holder"""
    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    OTHER = "other"


class Family(Base):
    """Family/household for multi-tenant expense tracking"""
    __tablename__ = "families"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    members = relationship("FamilyMember", back_populates="family", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="family", cascade="all, delete-orphan")
    categories = relationship("ExpenseCategory", back_populates="family", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Family(id={self.id}, name={self.name})>"


class FamilyMember(Base):
    """Individual family member who can have expenses"""
    __tablename__ = "family_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # Null for non-user dependents
    name = Column(String(255), nullable=False)
    relationship = Column(Enum(FamilyMemberRelationship), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    is_tax_dependent = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    family = relationship("Family", back_populates="members")
    user = relationship("User", backref="family_members")
    transactions = relationship("Transaction", back_populates="family_member")

    def __repr__(self):
        return f"<FamilyMember(id={self.id}, name={self.name}, relationship={self.relationship})>"
