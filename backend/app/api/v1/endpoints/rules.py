"""HSA Rules Engine API endpoints.

Endpoints:
  GET    /bank/rules                  → list rules ordered by priority
  POST   /bank/rules                  → create rule
  GET    /bank/rules/{rule_id}        → single rule
  PUT    /bank/rules/{rule_id}        → full replace
  DELETE /bank/rules/{rule_id}        → 204
  PATCH  /bank/rules/reorder          → reorder rules
  POST   /bank/rules/apply            → run engine on all user transactions
"""

import uuid as uuid_module
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.bank import BankConnection, BankTransaction
from app.models.rules import HsaRule, HsaRuleAction, HsaRuleCondition
from app.models.user import User
from app.services.rules_engine import (
    apply_auto_flag,
    apply_rules_to_transaction,
    get_active_rules_for_user,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RuleConditionIn(BaseModel):
    field: Literal["counterparty_name", "description", "amount", "date"]
    operator: Literal["is", "contains", "does_not_contain", "is_not", "eq", "gt", "lt", "before", "after"]
    value: str


class RuleActionIn(BaseModel):
    action_type: Literal["mark_hsa", "mark_potential", "hide", "assign_member"]
    member_id: Optional[UUID] = None


class HsaRuleIn(BaseModel):
    name: str
    priority: int = 0
    is_active: bool = True
    conditions: list[RuleConditionIn]
    actions: list[RuleActionIn]

    @field_validator("conditions")
    @classmethod
    def at_least_one_condition(cls, v):
        if len(v) < 1:
            raise ValueError("At least one condition is required.")
        return v

    @field_validator("actions")
    @classmethod
    def at_least_one_action(cls, v):
        if len(v) < 1:
            raise ValueError("At least one action is required.")
        return v


class RuleConditionResponse(BaseModel):
    id: UUID
    rule_id: UUID
    field: str
    operator: str
    value: str
    created_at: datetime

    class Config:
        from_attributes = True


class RuleActionResponse(BaseModel):
    id: UUID
    rule_id: UUID
    action_type: str
    member_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class HsaRuleResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    priority: int
    is_active: bool
    conditions: list[RuleConditionResponse]
    actions: list[RuleActionResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReorderItem(BaseModel):
    id: UUID
    priority: int


class ApplyResult(BaseModel):
    updated: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_rule_or_404(rule_id: UUID, user: User, db: Session) -> HsaRule:
    rule = (
        db.query(HsaRule)
        .filter(HsaRule.id == rule_id, HsaRule.user_id == user.id)
        .options(selectinload(HsaRule.conditions), selectinload(HsaRule.actions))
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found.")
    return rule


def _create_conditions_actions(rule: HsaRule, payload: HsaRuleIn, db: Session) -> None:
    for c in payload.conditions:
        db.add(HsaRuleCondition(
            id=uuid_module.uuid4(),
            rule_id=rule.id,
            field=c.field,
            operator=c.operator,
            value=c.value,
            created_at=datetime.utcnow(),
        ))
    for a in payload.actions:
        db.add(HsaRuleAction(
            id=uuid_module.uuid4(),
            rule_id=rule.id,
            action_type=a.action_type,
            member_id=a.member_id,
            created_at=datetime.utcnow(),
        ))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/rules", response_model=list[HsaRuleResponse])
async def list_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all rules for the current user, ordered by priority."""
    rules = (
        db.query(HsaRule)
        .filter(HsaRule.user_id == current_user.id)
        .options(selectinload(HsaRule.conditions), selectinload(HsaRule.actions))
        .order_by(HsaRule.priority.asc(), HsaRule.created_at.asc())
        .all()
    )
    return rules


@router.post("/rules", response_model=HsaRuleResponse, status_code=201)
async def create_rule(
    payload: HsaRuleIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new HSA rule with conditions and actions."""
    now = datetime.utcnow()
    rule = HsaRule(
        id=uuid_module.uuid4(),
        user_id=current_user.id,
        name=payload.name,
        priority=payload.priority,
        is_active=payload.is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    db.flush()  # get rule.id
    _create_conditions_actions(rule, payload, db)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules/reorder", response_model=list[HsaRuleResponse])
async def _placeholder():  # pragma: no cover
    """Placeholder — prevents /rules/{rule_id} from matching the path 'reorder'."""
    pass  # never reached; PATCH overrides


@router.get("/rules/{rule_id}", response_model=HsaRuleResponse)
async def get_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single rule by ID."""
    return _get_rule_or_404(rule_id, current_user, db)


@router.put("/rules/{rule_id}", response_model=HsaRuleResponse)
async def update_rule(
    rule_id: UUID,
    payload: HsaRuleIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full replace: update name/priority/is_active, delete and reinsert conditions+actions."""
    rule = _get_rule_or_404(rule_id, current_user, db)

    rule.name = payload.name
    rule.priority = payload.priority
    rule.is_active = payload.is_active
    rule.updated_at = datetime.utcnow()

    # Delete existing conditions and actions
    db.query(HsaRuleCondition).filter(HsaRuleCondition.rule_id == rule.id).delete()
    db.query(HsaRuleAction).filter(HsaRuleAction.rule_id == rule.id).delete()
    db.flush()

    _create_conditions_actions(rule, payload, db)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a rule and all its conditions and actions."""
    rule = _get_rule_or_404(rule_id, current_user, db)
    db.delete(rule)
    db.commit()


@router.patch("/rules/reorder", response_model=list[HsaRuleResponse])
async def reorder_rules(
    items: list[ReorderItem],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Batch-update priorities.  Body: [{id, priority}, ...]"""
    for item in items:
        rule = db.query(HsaRule).filter(
            HsaRule.id == item.id,
            HsaRule.user_id == current_user.id,
        ).first()
        if rule:
            rule.priority = item.priority
            rule.updated_at = datetime.utcnow()

    db.commit()

    return (
        db.query(HsaRule)
        .filter(HsaRule.user_id == current_user.id)
        .options(selectinload(HsaRule.conditions), selectinload(HsaRule.actions))
        .order_by(HsaRule.priority.asc(), HsaRule.created_at.asc())
        .all()
    )


@router.post("/rules/apply", response_model=ApplyResult)
async def apply_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the rules engine over all transactions for the current user.

    Returns the number of transactions that were updated.
    """
    # Fetch active rules for user
    rules = get_active_rules_for_user(current_user.id, db)

    # Find all transactions accessible to this user
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id == current_user.id, BankConnection.is_active == True)  # noqa: E712
        .subquery()
    )
    txns = (
        db.query(BankTransaction)
        .filter(BankTransaction.connection_id.in_(user_connection_ids))
        .all()
    )

    updated = 0
    for txn in txns:
        old_auto_flag = txn.auto_flag
        old_rule_id = txn.rule_id
        old_is_hsa = txn.is_hsa_eligible
        old_member = txn.family_member_id

        apply_auto_flag(txn)
        apply_rules_to_transaction(txn, rules)

        if (
            txn.auto_flag != old_auto_flag
            or txn.rule_id != old_rule_id
            or txn.is_hsa_eligible != old_is_hsa
            or txn.family_member_id != old_member
        ):
            updated += 1

    if updated:
        db.commit()

    return ApplyResult(updated=updated)