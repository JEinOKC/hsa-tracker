"""Household / family group models for shared account access."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Household(Base):
    __tablename__ = "households"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    roles = relationship("HouseholdRole", back_populates="household", cascade="all, delete-orphan")
    members = relationship("HouseholdMembership", back_populates="household", cascade="all, delete-orphan")


class HouseholdRole(Base):
    __tablename__ = "household_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)

    # Transactions
    can_read_transactions = Column(Boolean, default=True, nullable=False)
    can_write_transactions = Column(Boolean, default=False, nullable=False)
    can_delete_transactions = Column(Boolean, default=False, nullable=False)

    # Bank accounts
    can_read_bank_accounts = Column(Boolean, default=True, nullable=False)
    can_write_bank_accounts = Column(Boolean, default=False, nullable=False)
    can_delete_bank_accounts = Column(Boolean, default=False, nullable=False)

    # Documents
    can_read_documents = Column(Boolean, default=True, nullable=False)
    can_write_documents = Column(Boolean, default=False, nullable=False)
    can_delete_documents = Column(Boolean, default=False, nullable=False)

    # Family members
    can_read_family_members = Column(Boolean, default=True, nullable=False)
    can_write_family_members = Column(Boolean, default=False, nullable=False)
    can_delete_family_members = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    household = relationship("Household", back_populates="roles")
    memberships = relationship("HouseholdMembership", back_populates="role")


class HouseholdMembership(Base):
    __tablename__ = "household_memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("household_roles.id", ondelete="RESTRICT"), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_household_membership"),
    )

    household = relationship("Household", back_populates="members")
    user = relationship("User")
    role = relationship("HouseholdRole", back_populates="memberships")
