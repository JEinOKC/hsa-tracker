"""HSA Rules Engine — auto-flag and rule evaluation logic."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.bank import BankTransaction
from app.models.rules import HsaRule, HsaRuleCondition, HsaRuleAction
from app.services.merchant_keywords import (
    classify_merchant,
    normalize_merchant_name,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Teller category values that suggest potential HSA eligibility.
# Expand this list as more patterns are discovered.
POTENTIAL_HSA_CATEGORIES: frozenset[str] = frozenset({
    "health",         # Teller's primary medical/pharmacy category
    "personal_care",  # pharmacies, vision, hearing aids
    "mental_health",  # therapy, counseling
    "fitness",        # gym memberships (sometimes HSA-eligible)
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_auto_flag(txn: BankTransaction) -> None:
    """Set auto_flag='potential_hsa' if the transaction looks HSA-eligible
    and the user hasn't reviewed it yet.

    Two signals are checked (either is sufficient):
      1. Teller category is in POTENTIAL_HSA_CATEGORIES.
      2. Normalized merchant name matches HSA_LIKELY_KEYWORDS (catches cases
         where Teller miscategorizes a medical provider).
    """
    if txn.is_hsa_eligible is not None:
        return
    category = _safe_details_category(txn)
    if category in POTENTIAL_HSA_CATEGORIES:
        txn.auto_flag = "potential_hsa"
        return
    merchant_raw = _safe_counterparty_name(txn)
    if merchant_raw:
        normalized = normalize_merchant_name(merchant_raw)
        if classify_merchant(normalized) == "likely":
            txn.auto_flag = "potential_hsa"


def apply_rules_to_transaction(txn: BankTransaction, rules: list[HsaRule]) -> None:
    """Evaluate rules in ascending priority order; first full match wins.

    All conditions within a rule must pass (AND logic).  When a match is found
    all of its actions are applied, ``rule_id`` is set, and evaluation stops.
    """
    for rule in rules:
        if _rule_matches(txn, rule):
            _apply_actions(txn, rule)
            txn.rule_id = rule.id
            return


def would_rule_apply(
    txn: BankTransaction,
    test_rule: HsaRule,
    higher_priority_rules: list[HsaRule],
) -> bool:
    """Return True if *test_rule* would be the first matching rule for *txn*.

    Checks that no rule in *higher_priority_rules* already claims the transaction.
    """
    for rule in higher_priority_rules:
        if _rule_matches(txn, rule):
            return False
    return _rule_matches(txn, test_rule)


def get_active_rules_for_user(user_id: UUID, db: Session) -> list[HsaRule]:
    """Return active rules for *user_id* ordered by priority ASC."""
    return (
        db.query(HsaRule)
        .filter(HsaRule.user_id == user_id, HsaRule.is_active == True)  # noqa: E712
        .options(selectinload(HsaRule.conditions), selectinload(HsaRule.actions))
        .order_by(HsaRule.priority.asc(), HsaRule.created_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_details_category(txn: BankTransaction) -> Optional[str]:
    """Extract the top-level 'category' key from txn.details, or None."""
    try:
        details = txn.details
        if not details or not isinstance(details, dict):
            return None
        return details.get("category")
    except Exception:
        return None


def _safe_counterparty_name(txn: BankTransaction) -> str:
    """Extract details['counterparty']['name'], defaulting to ''."""
    try:
        details = txn.details
        if not details or not isinstance(details, dict):
            return ""
        cp = details.get("counterparty")
        if not cp or not isinstance(cp, dict):
            return ""
        return cp.get("name") or ""
    except Exception:
        return ""


def _rule_matches(txn: BankTransaction, rule: HsaRule) -> bool:
    """Return True only if ALL conditions in *rule* evaluate to True."""
    for condition in rule.conditions:
        if not _evaluate_condition(txn, condition):
            return False
    return True


def _evaluate_condition(txn: BankTransaction, condition: HsaRuleCondition) -> bool:
    """Evaluate a single condition against *txn*.

    Supported fields:
      - counterparty_name  → string extracted from details
      - description        → txn.description (str)
      - amount             → txn.amount (float)
      - date               → txn.transaction_date (date)

    Supported operators per type:
      - text:   is, contains, does_not_contain, is_not
      - amount: eq, gt, lt
      - date:   before, after
    """
    field = condition.field
    operator = condition.operator
    value = condition.value

    try:
        if field == "counterparty_name":
            return _eval_text(_safe_counterparty_name(txn), operator, value)

        if field == "description":
            return _eval_text(txn.description or "", operator, value)

        if field == "teller_category":
            return _eval_text(_safe_details_category(txn) or "", operator, value)

        if field == "amount":
            try:
                txn_amount = float(txn.amount)
                cond_amount = float(value)
            except (TypeError, ValueError):
                return False
            return _eval_numeric(txn_amount, operator, cond_amount)

        if field == "date":
            txn_date: Optional[date] = txn.transaction_date
            if txn_date is None:
                return False
            try:
                cond_date = date.fromisoformat(value)
            except ValueError:
                return False
            return _eval_date(txn_date, operator, cond_date)

    except Exception:
        return False

    return False


def _eval_text(field_value: str, operator: str, cond_value: str) -> bool:
    fv = field_value.lower()
    cv = cond_value.lower()
    if operator == "is":
        return fv == cv
    if operator == "is_not":
        return fv != cv
    if operator == "contains":
        return cv in fv
    if operator == "does_not_contain":
        return cv not in fv
    return False


def _eval_numeric(txn_amount: float, operator: str, cond_amount: float) -> bool:
    if operator == "eq":
        return txn_amount == cond_amount
    if operator == "gt":
        return txn_amount > cond_amount
    if operator == "lt":
        return txn_amount < cond_amount
    return False


def _eval_date(txn_date: date, operator: str, cond_date: date) -> bool:
    if operator == "before":
        return txn_date < cond_date
    if operator == "after":
        return txn_date > cond_date
    return False


def _apply_actions(txn: BankTransaction, rule: HsaRule) -> None:
    """Apply all actions from a matching rule, respecting manual-override semantics."""
    for action in rule.actions:
        action_type = action.action_type

        if action_type == "mark_hsa":
            # Never overwrite a manual annotation
            if txn.is_hsa_eligible is None:
                txn.is_hsa_eligible = True

        elif action_type == "mark_potential":
            txn.auto_flag = "potential_hsa"

        elif action_type == "hide":
            txn.auto_flag = "hidden"

        elif action_type == "assign_member":
            # Never overwrite a manual assignment
            if txn.family_member_id is None and action.member_id is not None:
                txn.family_member_id = action.member_id