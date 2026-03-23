"""Family member models for HSA eligibility tracking."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class FamilyMember(Base):
    """A family member who may be tagged on HSA expenses."""

    __tablename__ = "family_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    # "self", "spouse", "child", "other" — column name avoids shadowing sqlalchemy.orm.relationship
    member_relationship = Column(String(50), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    is_tax_dependent = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    eligibility_periods = relationship(
        "HsaEligibilityPeriod",
        back_populates="family_member",
        cascade="all, delete-orphan",
        order_by="HsaEligibilityPeriod.start_date",
    )

    def __repr__(self):
        return f"<FamilyMember({self.name} — {self.member_relationship})>"


class HsaEligibilityPeriod(Base):
    """A date range during which a family member is HSA-eligible.

    A member may have multiple non-overlapping periods (e.g., they lost
    HDHP coverage for a year and then regained it). When tagging a
    transaction, we check whether the expense date falls within any
    period for that member.
    """

    __tablename__ = "hsa_eligibility_periods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)      # NULL = still eligible / open-ended
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    family_member = relationship("FamilyMember", back_populates="eligibility_periods")

    def __repr__(self):
        end = self.end_date or "present"
        return f"<HsaEligibilityPeriod({self.start_date} → {end})>"
