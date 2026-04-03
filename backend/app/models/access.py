"""Role-based account access models"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AccountRole(Base):
    """A named permission set defined by an account owner."""

    __tablename__ = "account_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # e.g. "Spouse", "Accountant"

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

    # Relationships
    accesses = relationship("AccountAccess", back_populates="role", cascade="all, delete-orphan")


class AccountAccess(Base):
    """Links a sub-user to a role on an account owner's data."""

    __tablename__ = "account_accesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("account_roles.id", ondelete="CASCADE"), nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_user_id", "sub_user_id", name="uq_access_owner_sub"),
    )

    # Relationships
    role = relationship("AccountRole", back_populates="accesses")
