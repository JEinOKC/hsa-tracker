"""Unit tests for the HSA Rules Engine service.

No database required — all objects are plain Python instances.
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from app.services.rules_engine import (
    _evaluate_condition,
    apply_auto_flag,
    apply_rules_to_transaction,
    would_rule_apply,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_txn(
    *,
    details=None,
    is_hsa_eligible=None,
    family_member_id=None,
    description="CVS Pharmacy",
    amount="-42.00",
    transaction_date=None,
    auto_flag=None,
    rule_id=None,
):
    txn = MagicMock()
    txn.details = details
    txn.is_hsa_eligible = is_hsa_eligible
    txn.family_member_id = family_member_id
    txn.description = description
    txn.amount = Decimal(amount)
    txn.transaction_date = transaction_date or date(2026, 3, 1)
    txn.auto_flag = auto_flag
    txn.rule_id = rule_id
    return txn


def _make_condition(field: str, operator: str, value: str):
    cond = MagicMock()
    cond.field = field
    cond.operator = operator
    cond.value = value
    return cond


def _make_action(action_type: str, member_id=None):
    action = MagicMock()
    action.action_type = action_type
    action.member_id = member_id
    return action


def _make_rule(conditions, actions, priority=0):
    rule = MagicMock()
    rule.id = uuid.uuid4()
    rule.priority = priority
    rule.conditions = conditions
    rule.actions = actions
    return rule


# ---------------------------------------------------------------------------
# apply_auto_flag
# ---------------------------------------------------------------------------


class TestApplyAutoFlag:
    def test_sets_potential_hsa_when_category_health_and_eligible_null(self):
        txn = _make_txn(
            details={"category": "health"},
            is_hsa_eligible=None,
        )
        apply_auto_flag(txn)
        assert txn.auto_flag == "potential_hsa"

    def test_no_change_when_is_hsa_eligible_is_true(self):
        txn = _make_txn(
            details={"category": "health"},
            is_hsa_eligible=True,
        )
        apply_auto_flag(txn)
        assert txn.auto_flag is None  # unchanged (was None before call)

    def test_no_change_when_is_hsa_eligible_is_false(self):
        txn = _make_txn(
            details={"category": "health"},
            is_hsa_eligible=False,
        )
        apply_auto_flag(txn)
        assert txn.auto_flag is None

    def test_no_change_when_category_is_not_health(self):
        txn = _make_txn(
            details={"category": "food"},
            is_hsa_eligible=None,
            description="AMAZON MARKETPLACE",
        )
        apply_auto_flag(txn)
        assert txn.auto_flag is None

    def test_no_change_when_details_is_none(self):
        txn = _make_txn(details=None, is_hsa_eligible=None, description="AMAZON MARKETPLACE")
        apply_auto_flag(txn)
        assert txn.auto_flag is None

    def test_no_change_when_details_missing_category_key(self):
        # Use a merchant that isn't in either keyword list so only the category
        # path is exercised. "AMAZON MARKETPLACE" is classified 'unknown'.
        txn = _make_txn(details={"counterparty": {"name": "AMAZON MARKETPLACE"}}, is_hsa_eligible=None)
        apply_auto_flag(txn)
        assert txn.auto_flag is None

    def test_handles_non_dict_details_gracefully(self):
        txn = _make_txn(details="unexpected string", is_hsa_eligible=None, description="AMAZON MARKETPLACE")
        apply_auto_flag(txn)
        assert txn.auto_flag is None

    def test_unlikely_merchant_does_not_set_auto_flag(self):
        # NON_HSA filtering is query-time, not written to DB — apply_auto_flag leaves these alone
        txn = _make_txn(
            details={"counterparty": {"name": "MCDONALD'S"}},
            is_hsa_eligible=None,
        )
        apply_auto_flag(txn)
        assert txn.auto_flag is None

    def test_non_hsa_category_does_not_set_auto_flag(self):
        # NON_HSA filtering is query-time — apply_auto_flag leaves unreviewed food txns alone
        txn = _make_txn(
            details={"category": "food_and_drink", "counterparty": {"name": "AMAZON MARKETPLACE"}},
            is_hsa_eligible=None,
        )
        apply_auto_flag(txn)
        assert txn.auto_flag is None

    def test_likely_merchant_still_flagged_despite_non_hsa_category(self):
        # Walgreens miscategorized as food_and_drink → still potential_hsa via keyword
        txn = _make_txn(
            details={"category": "food_and_drink", "counterparty": {"name": "WALGREENS"}},
            is_hsa_eligible=None,
        )
        apply_auto_flag(txn)
        assert txn.auto_flag == "potential_hsa"


# ---------------------------------------------------------------------------
# _evaluate_condition — text fields
# ---------------------------------------------------------------------------


class TestEvaluateConditionText:
    def test_description_is_exact_match(self):
        txn = _make_txn(description="CVS Pharmacy")
        cond = _make_condition("description", "is", "CVS Pharmacy")
        assert _evaluate_condition(txn, cond) is True

    def test_description_is_case_insensitive(self):
        txn = _make_txn(description="CVS Pharmacy")
        cond = _make_condition("description", "is", "cvs pharmacy")
        assert _evaluate_condition(txn, cond) is True

    def test_description_is_not(self):
        txn = _make_txn(description="Walgreens")
        cond = _make_condition("description", "is_not", "CVS Pharmacy")
        assert _evaluate_condition(txn, cond) is True

    def test_description_is_not_fails_when_equal(self):
        txn = _make_txn(description="CVS Pharmacy")
        cond = _make_condition("description", "is_not", "CVS Pharmacy")
        assert _evaluate_condition(txn, cond) is False

    def test_description_contains(self):
        txn = _make_txn(description="CVS Pharmacy Store #123")
        cond = _make_condition("description", "contains", "CVS")
        assert _evaluate_condition(txn, cond) is True

    def test_description_contains_no_match(self):
        txn = _make_txn(description="Walgreens")
        cond = _make_condition("description", "contains", "CVS")
        assert _evaluate_condition(txn, cond) is False

    def test_description_does_not_contain(self):
        txn = _make_txn(description="Walgreens")
        cond = _make_condition("description", "does_not_contain", "CVS")
        assert _evaluate_condition(txn, cond) is True

    def test_description_does_not_contain_fails_when_present(self):
        txn = _make_txn(description="CVS Pharmacy")
        cond = _make_condition("description", "does_not_contain", "CVS")
        assert _evaluate_condition(txn, cond) is False

    def test_description_none_treated_as_empty_string(self):
        txn = _make_txn(description=None)
        cond = _make_condition("description", "contains", "CVS")
        assert _evaluate_condition(txn, cond) is False

    def test_counterparty_name_contains(self):
        txn = _make_txn(details={"counterparty": {"name": "CVS Health"}})
        cond = _make_condition("counterparty_name", "contains", "cvs")
        assert _evaluate_condition(txn, cond) is True

    def test_counterparty_name_falls_back_to_description(self):
        # When counterparty is absent the description is used as fallback
        txn = _make_txn(details={}, description="CVS Pharmacy")
        cond = _make_condition("counterparty_name", "contains", "cvs")
        assert _evaluate_condition(txn, cond) is True

    def test_counterparty_name_missing_no_description_match(self):
        txn = _make_txn(details={}, description="AMAZON MARKETPLACE")
        cond = _make_condition("counterparty_name", "contains", "cvs")
        assert _evaluate_condition(txn, cond) is False

    def test_counterparty_name_missing_counterparty_key(self):
        txn = _make_txn(details={"category": "health"}, description="AMAZON MARKETPLACE")
        cond = _make_condition("counterparty_name", "is", "CVS")
        assert _evaluate_condition(txn, cond) is False


# ---------------------------------------------------------------------------
# _evaluate_condition — amount
# ---------------------------------------------------------------------------


class TestEvaluateConditionAmount:
    def test_amount_eq(self):
        txn = _make_txn(amount="-42.00")
        cond = _make_condition("amount", "eq", "-42.00")
        assert _evaluate_condition(txn, cond) is True

    def test_amount_eq_fails(self):
        txn = _make_txn(amount="-42.00")
        cond = _make_condition("amount", "eq", "-43.00")
        assert _evaluate_condition(txn, cond) is False

    def test_amount_gt(self):
        txn = _make_txn(amount="-10.00")
        cond = _make_condition("amount", "gt", "-50.00")
        assert _evaluate_condition(txn, cond) is True

    def test_amount_lt(self):
        txn = _make_txn(amount="-100.00")
        cond = _make_condition("amount", "lt", "-50.00")
        assert _evaluate_condition(txn, cond) is True

    def test_amount_invalid_value_returns_false(self):
        txn = _make_txn(amount="-42.00")
        cond = _make_condition("amount", "eq", "not-a-number")
        assert _evaluate_condition(txn, cond) is False


# ---------------------------------------------------------------------------
# _evaluate_condition — date
# ---------------------------------------------------------------------------


class TestEvaluateConditionDate:
    def test_date_before(self):
        txn = _make_txn(transaction_date=date(2026, 1, 1))
        cond = _make_condition("date", "before", "2026-06-01")
        assert _evaluate_condition(txn, cond) is True

    def test_date_before_fails_when_same(self):
        txn = _make_txn(transaction_date=date(2026, 6, 1))
        cond = _make_condition("date", "before", "2026-06-01")
        assert _evaluate_condition(txn, cond) is False

    def test_date_after(self):
        txn = _make_txn(transaction_date=date(2026, 12, 1))
        cond = _make_condition("date", "after", "2026-06-01")
        assert _evaluate_condition(txn, cond) is True

    def test_date_invalid_format_returns_false(self):
        txn = _make_txn(transaction_date=date(2026, 3, 1))
        cond = _make_condition("date", "before", "not-a-date")
        assert _evaluate_condition(txn, cond) is False

    def test_date_none_returns_false(self):
        txn = _make_txn()
        txn.transaction_date = None
        cond = _make_condition("date", "before", "2026-06-01")
        assert _evaluate_condition(txn, cond) is False


# ---------------------------------------------------------------------------
# apply_rules_to_transaction
# ---------------------------------------------------------------------------


class TestApplyRulesToTransaction:
    def test_first_matching_rule_wins(self):
        """When two rules both match, only the first (lower priority) applies."""
        txn = _make_txn(description="CVS Pharmacy", is_hsa_eligible=None)

        rule1 = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("mark_hsa")],
            priority=0,
        )
        rule2 = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("mark_potential")],
            priority=1,
        )

        apply_rules_to_transaction(txn, [rule1, rule2])

        # mark_hsa from rule1 was applied
        assert txn.is_hsa_eligible is True
        assert txn.rule_id == rule1.id

    def test_no_match_leaves_txn_unchanged(self):
        txn = _make_txn(description="Amazon", is_hsa_eligible=None, auto_flag=None, rule_id=None)

        rule = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("mark_hsa")],
        )

        apply_rules_to_transaction(txn, [rule])

        assert txn.is_hsa_eligible is None
        assert txn.rule_id is None

    def test_all_conditions_must_match_and_logic(self):
        """A rule with two conditions only fires when BOTH match."""
        txn = _make_txn(description="CVS Pharmacy", amount="-42.00", is_hsa_eligible=None)

        rule = _make_rule(
            conditions=[
                _make_condition("description", "contains", "CVS"),
                _make_condition("amount", "lt", "-100.00"),  # amount is -42, NOT < -100
            ],
            actions=[_make_action("mark_hsa")],
        )

        apply_rules_to_transaction(txn, [rule])

        # Second condition fails → rule doesn't match
        assert txn.is_hsa_eligible is None

    def test_all_conditions_match_fires_rule(self):
        txn = _make_txn(description="CVS Pharmacy", amount="-42.00", is_hsa_eligible=None)

        rule = _make_rule(
            conditions=[
                _make_condition("description", "contains", "CVS"),
                _make_condition("amount", "gt", "-100.00"),  # -42 > -100 ✓
            ],
            actions=[_make_action("mark_hsa")],
        )

        apply_rules_to_transaction(txn, [rule])
        assert txn.is_hsa_eligible is True

    def test_mark_hsa_does_not_overwrite_non_null_is_hsa_eligible(self):
        txn = _make_txn(description="CVS Pharmacy", is_hsa_eligible=False)

        rule = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("mark_hsa")],
        )

        apply_rules_to_transaction(txn, [rule])

        # Manual False was preserved
        assert txn.is_hsa_eligible is False
        # rule_id still set (rule fired, but action respected manual value)
        assert txn.rule_id == rule.id

    def test_assign_member_does_not_overwrite_existing(self):
        existing_member = uuid.uuid4()
        new_member = uuid.uuid4()
        txn = _make_txn(description="CVS Pharmacy", family_member_id=existing_member)

        rule = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("assign_member", member_id=new_member)],
        )

        apply_rules_to_transaction(txn, [rule])

        assert txn.family_member_id == existing_member  # unchanged

    def test_assign_member_sets_when_none(self):
        new_member = uuid.uuid4()
        txn = _make_txn(description="CVS Pharmacy", family_member_id=None)

        rule = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("assign_member", member_id=new_member)],
        )

        apply_rules_to_transaction(txn, [rule])
        assert txn.family_member_id == new_member

    def test_multiple_actions_all_applied(self):
        """A rule can have both mark_potential and assign_member; both fire."""
        member_id = uuid.uuid4()
        txn = _make_txn(description="CVS Pharmacy", is_hsa_eligible=None, family_member_id=None)

        rule = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[
                _make_action("mark_potential"),
                _make_action("assign_member", member_id=member_id),
            ],
        )

        apply_rules_to_transaction(txn, [rule])

        assert txn.auto_flag == "potential_hsa"
        assert txn.family_member_id == member_id
        assert txn.rule_id == rule.id

    def test_hide_action_sets_auto_flag_hidden(self):
        txn = _make_txn(description="random junk")

        rule = _make_rule(
            conditions=[_make_condition("description", "contains", "junk")],
            actions=[_make_action("hide")],
        )

        apply_rules_to_transaction(txn, [rule])
        assert txn.auto_flag == "hidden"

    def test_empty_rules_list_is_no_op(self):
        txn = _make_txn(description="CVS Pharmacy", is_hsa_eligible=None)
        apply_rules_to_transaction(txn, [])
        assert txn.is_hsa_eligible is None
        assert txn.rule_id is None

    def test_rule_id_set_on_match(self):
        txn = _make_txn(description="CVS Pharmacy")
        rule_id = uuid.uuid4()
        rule = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("mark_potential")],
        )
        rule.id = rule_id

        apply_rules_to_transaction(txn, [rule])
        assert txn.rule_id == rule_id


# ---------------------------------------------------------------------------
# would_rule_apply
# ---------------------------------------------------------------------------


class TestWouldRuleApply:
    def _cvs_rule(self):
        return _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("mark_hsa")],
        )

    def test_applies_when_no_higher_priority_rules(self):
        txn = _make_txn(description="CVS Pharmacy")
        assert would_rule_apply(txn, self._cvs_rule(), []) is True

    def test_does_not_apply_when_condition_not_met(self):
        txn = _make_txn(description="Starbucks")
        assert would_rule_apply(txn, self._cvs_rule(), []) is False

    def test_does_not_apply_when_higher_priority_rule_matches(self):
        txn = _make_txn(description="CVS Pharmacy")
        higher = _make_rule(
            conditions=[_make_condition("description", "contains", "CVS")],
            actions=[_make_action("mark_hsa")],
        )
        assert would_rule_apply(txn, self._cvs_rule(), [higher]) is False

    def test_applies_when_higher_priority_rule_does_not_match(self):
        txn = _make_txn(description="CVS Pharmacy")
        higher = _make_rule(
            conditions=[_make_condition("description", "contains", "Walgreens")],
            actions=[_make_action("mark_hsa")],
        )
        assert would_rule_apply(txn, self._cvs_rule(), [higher]) is True


# ---------------------------------------------------------------------------
# apply_auto_flag — POTENTIAL_HSA_CATEGORIES dictionary
# ---------------------------------------------------------------------------


class TestApplyAutoFlagCategories:
    """Verify all members of POTENTIAL_HSA_CATEGORIES trigger potential_hsa."""

    @pytest.mark.parametrize("category", ["health", "personal_care", "mental_health", "fitness"])
    def test_potential_hsa_categories_trigger_flag(self, category):
        txn = _make_txn(details={"category": category}, is_hsa_eligible=None)
        apply_auto_flag(txn)
        assert txn.auto_flag == "potential_hsa", f"Expected potential_hsa for category={category!r}"

    @pytest.mark.parametrize("category", ["food_and_drink", "travel", "entertainment", "fuel", "gambling", "subscription", "shopping", "transportation", "other"])
    def test_non_potential_hsa_categories_do_not_set_auto_flag(self, category):
        # NON_HSA filtering happens at query time; apply_auto_flag leaves these untouched
        txn = _make_txn(details={"category": category}, is_hsa_eligible=None, description="AMAZON MARKETPLACE")
        apply_auto_flag(txn)
        assert txn.auto_flag is None, f"Expected no flag for category={category!r}"


# ---------------------------------------------------------------------------
# _evaluate_condition — provider_category field
# ---------------------------------------------------------------------------


class TestEvaluateConditionTellerCategory:
    def test_provider_category_is_exact_match(self):
        txn = _make_txn(details={"category": "health"})
        cond = _make_condition("provider_category", "is", "health")
        assert _evaluate_condition(txn, cond) is True

    def test_provider_category_is_case_insensitive(self):
        txn = _make_txn(details={"category": "Health"})
        cond = _make_condition("provider_category", "is", "health")
        assert _evaluate_condition(txn, cond) is True

    def test_provider_category_is_not(self):
        txn = _make_txn(details={"category": "shopping"})
        cond = _make_condition("provider_category", "is_not", "health")
        assert _evaluate_condition(txn, cond) is True

    def test_provider_category_is_not_fails_when_equal(self):
        txn = _make_txn(details={"category": "health"})
        cond = _make_condition("provider_category", "is_not", "health")
        assert _evaluate_condition(txn, cond) is False

    def test_provider_category_contains(self):
        txn = _make_txn(details={"category": "personal_care"})
        cond = _make_condition("provider_category", "contains", "care")
        assert _evaluate_condition(txn, cond) is True

    def test_provider_category_does_not_contain(self):
        txn = _make_txn(details={"category": "shopping"})
        cond = _make_condition("provider_category", "does_not_contain", "health")
        assert _evaluate_condition(txn, cond) is True

    def test_provider_category_missing_details_returns_false_for_is(self):
        txn = _make_txn(details=None)
        cond = _make_condition("provider_category", "is", "health")
        assert _evaluate_condition(txn, cond) is False

    def test_provider_category_missing_category_key_returns_false(self):
        txn = _make_txn(details={"counterparty": {"name": "CVS"}})
        cond = _make_condition("provider_category", "is", "health")
        assert _evaluate_condition(txn, cond) is False

    def test_provider_category_missing_does_not_contain_returns_true(self):
        """Empty string does not contain 'health' → condition passes."""
        txn = _make_txn(details=None)
        cond = _make_condition("provider_category", "does_not_contain", "health")
        assert _evaluate_condition(txn, cond) is True

    def test_provider_category_rule_fires_on_matching_category(self):
        """End-to-end: a hide rule on food_and_drink hides matching transactions."""
        txn = _make_txn(details={"category": "food_and_drink"}, is_hsa_eligible=None)

        rule = _make_rule(
            conditions=[_make_condition("provider_category", "is", "food_and_drink")],
            actions=[_make_action("hide")],
        )

        apply_rules_to_transaction(txn, [rule])
        assert txn.auto_flag == "hidden"

    def test_provider_category_rule_does_not_fire_on_different_category(self):
        txn = _make_txn(details={"category": "health"}, is_hsa_eligible=None)

        rule = _make_rule(
            conditions=[_make_condition("provider_category", "is", "food_and_drink")],
            actions=[_make_action("hide")],
        )

        apply_rules_to_transaction(txn, [rule])
        assert txn.auto_flag is None
