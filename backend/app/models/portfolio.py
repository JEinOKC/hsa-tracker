"""HSA investment portfolio models — manual-entry holdings and account tracking."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class HsaAccount(Base):
    """A manually-tracked HSA institution account (e.g. Fidelity HSA, Rippling HSA)."""

    __tablename__ = "hsa_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    institution_name = Column(String(255), nullable=False)
    nickname = Column(String(255), nullable=True)
    account_type = Column(
        String(20),
        nullable=False,
        default="both",
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Manually entered cash (uninvested) balance
    cash_balance = Column(Numeric(12, 2), nullable=True)
    cash_balance_updated_at = Column(DateTime, nullable=True)

    # Timestamp of the last time the user confirmed the account values are current
    last_checkin_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    holdings = relationship(
        "HsaHolding",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "account_type IN ('contribution', 'investment', 'both')",
            name="ck_hsa_account_type",
        ),
    )

    def __repr__(self):
        return f"<HsaAccount({self.institution_name!r} — {self.nickname or 'no nickname'})>"


class HsaHolding(Base):
    """A stock or fund position within an HsaAccount."""

    __tablename__ = "hsa_holdings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hsa_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker = Column(String(20), nullable=False)
    shares = Column(Numeric(16, 6), nullable=False)

    # Populated by the price-fetch service; null until first fetch
    last_known_price = Column(Numeric(12, 4), nullable=True)
    last_price_fetched_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("HsaAccount", back_populates="holdings")

    def __repr__(self):
        return f"<HsaHolding({self.ticker} × {self.shares})>"
