"""Bank connection and transaction models for provider-ingested data."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BankConnection(Base):
    """A bank account connected via an external provider (Teller, etc.)."""

    __tablename__ = "bank_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider = Column(String(50), nullable=False)           # "teller"
    provider_account_id = Column(String(255), nullable=False, index=True)
    account_name = Column(String(255), nullable=False)
    account_type = Column(String(50))                       # "depository", "credit"
    account_subtype = Column(String(50))                    # "checking", "savings", "hsa", etc.
    institution_name = Column(String(255))
    last_four = Column(String(4))
    enrollment_token = Column(String(255), nullable=True)           # Teller Connect access token
    currency = Column(String(3), default="USD", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    transactions = relationship(
        "BankTransaction",
        back_populates="connection",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_bank_connection_provider_account"),
    )

    def __repr__(self):
        return f"<BankConnection({self.provider}:{self.provider_account_id} — {self.account_name})>"


class BankTransaction(Base):
    """A bank transaction — either synced from a provider (Teller) or entered manually."""

    __tablename__ = "bank_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable for manual transactions that have no bank connection
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bank_connections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Direct user ownership — required for manual transactions (no connection to derive from)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # 'teller' for synced transactions, 'manual' for user-entered ones
    source = Column(String(20), nullable=False, server_default="teller")
    provider = Column(String(50), nullable=True)
    provider_transaction_id = Column(String(255), nullable=True, index=True)

    transaction_date = Column(Date, nullable=False, index=True)
    description = Column(String(500))
    amount = Column(Numeric(12, 2), nullable=False)         # negative = debit, positive = credit
    transaction_type = Column(String(50))                   # "card_payment", "ach", etc.
    status = Column(String(20), nullable=False)             # "posted", "pending"
    details = Column(JSON, nullable=True)                   # raw provider-specific fields

    # HSA annotations — set by the user on the Transactions page
    # NULL = unreviewed, True = HSA-eligible, False = not eligible
    is_hsa_eligible = Column(Boolean, nullable=True, index=True)
    family_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hsa_category = Column(String(100), nullable=True)       # "medical", "dental", etc.
    eligible_amount = Column(Numeric(12, 2), nullable=True) # partial HSA amount; None = use full amount
    reimbursement_status = Column(String(20), nullable=True) # "pending","reimbursed","not_needed"
    reimbursed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # Rules engine fields — set by auto-flag logic or user rules
    auto_flag = Column(String(20), nullable=True, index=True)  # 'potential_hsa' | 'hidden'
    rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hsa_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    connection = relationship("BankConnection", back_populates="transactions")
    family_member = relationship("FamilyMember", foreign_keys=[family_member_id])
    rule = relationship("HsaRule", foreign_keys=[rule_id])
    documents = relationship(
        "TransactionDocument",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        # Only enforce uniqueness for provider-synced rows (nulls are ignored by postgres unique constraints)
        UniqueConstraint(
            "connection_id",
            "provider_transaction_id",
            name="uq_bank_txn_connection_provider_id",
        ),
        CheckConstraint(
            "auto_flag IN ('potential_hsa', 'hidden') OR auto_flag IS NULL",
            name="ck_bank_txn_auto_flag",
        ),
        CheckConstraint(
            "source IN ('teller', 'manual')",
            name="ck_bank_txn_source",
        ),
    )

    def __repr__(self):
        return f"<BankTransaction({self.provider_transaction_id} {self.transaction_date} {self.amount})>"


class TransactionDocument(Base):
    """A receipt or supporting document attached to a bank transaction, stored in S3."""

    __tablename__ = "transaction_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bank_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    s3_key = Column(String(1024), nullable=False)
    original_filename = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # "pending" | "confirmed"
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("BankTransaction", back_populates="documents")

    def __repr__(self):
        return f"<TransactionDocument({self.original_filename} → {self.s3_key})>"


class UserCategoryOverride(Base):
    """Per-user Smart filter pin: force a Teller category to always show or always hide."""

    __tablename__ = "user_category_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = Column(String(100), nullable=False)
    pin_mode = Column(String(10), nullable=False)  # 'show' | 'hide'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_user_category_override_user_category"),
        CheckConstraint("pin_mode IN ('show', 'hide')", name="ck_user_category_override_pin_mode"),
    )
