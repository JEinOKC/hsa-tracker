"""Bank connection and transaction models for provider-ingested data."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BankConnection(Base):
    """A bank account connected via an external provider (Teller, etc.)."""

    __tablename__ = "bank_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    """A transaction imported from an external bank provider."""

    __tablename__ = "bank_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bank_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False)
    provider_transaction_id = Column(String(255), nullable=False, index=True)

    transaction_date = Column(Date, nullable=False, index=True)
    description = Column(String(500))
    amount = Column(Numeric(12, 2), nullable=False)         # negative = debit, positive = credit
    transaction_type = Column(String(50))                   # "card_payment", "ach", etc.
    status = Column(String(20), nullable=False)             # "posted", "pending"
    details = Column(JSON, nullable=True)                   # raw provider-specific fields

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    connection = relationship("BankConnection", back_populates="transactions")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "provider_transaction_id",
            name="uq_bank_txn_connection_provider_id",
        ),
    )

    def __repr__(self):
        return f"<BankTransaction({self.provider_transaction_id} {self.transaction_date} {self.amount})>"
