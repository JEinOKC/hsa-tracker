"""HSA Rules Engine models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class HsaRule(Base):
    """A user-configured rule that auto-annotates transactions."""

    __tablename__ = "hsa_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    priority = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    conditions = relationship(
        "HsaRuleCondition",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="HsaRuleCondition.id",
    )
    actions = relationship(
        "HsaRuleAction",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="HsaRuleAction.id",
    )

    def __repr__(self):
        return f"<HsaRule({self.name!r} priority={self.priority})>"


class HsaRuleCondition(Base):
    """A single condition within an HSA rule (all conditions are AND'd)."""

    __tablename__ = "hsa_rule_conditions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hsa_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # field: counterparty_name | description | amount | date
    field = Column(String(50), nullable=False)
    # operator: is | contains | does_not_contain | is_not | eq | gt | lt | before | after
    operator = Column(String(30), nullable=False)
    value = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rule = relationship("HsaRule", back_populates="conditions")

    __table_args__ = (
        CheckConstraint(
            "field IN ('counterparty_name', 'description', 'amount', 'date')",
            name="ck_hsa_rule_condition_field",
        ),
        CheckConstraint(
            "operator IN ('is', 'contains', 'does_not_contain', 'is_not', 'eq', 'gt', 'lt', 'before', 'after')",
            name="ck_hsa_rule_condition_operator",
        ),
    )

    def __repr__(self):
        return f"<HsaRuleCondition({self.field} {self.operator} {self.value!r})>"


class HsaRuleAction(Base):
    """A single action taken when a rule fires."""

    __tablename__ = "hsa_rule_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hsa_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # action_type: mark_hsa | mark_potential | hide | assign_member
    action_type = Column(String(30), nullable=False)
    # only for assign_member
    member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rule = relationship("HsaRule", back_populates="actions")
    member = relationship("FamilyMember", foreign_keys=[member_id])

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('mark_hsa', 'mark_potential', 'hide', 'assign_member')",
            name="ck_hsa_rule_action_type",
        ),
    )

    def __repr__(self):
        return f"<HsaRuleAction({self.action_type})>"