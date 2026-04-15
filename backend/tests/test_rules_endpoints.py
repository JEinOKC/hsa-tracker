"""Integration tests for HSA Rules Engine API endpoints.

Tests CRUD operations, auth guards, reorder, and apply endpoint.
"""

import uuid
from datetime import datetime

import pytest

from app.models.rules import HsaRule, HsaRuleCondition, HsaRuleAction
from app.models.bank import BankConnection, BankTransaction
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule_payload(
    name="Pharmacy Rule",
    priority=0,
    is_active=True,
    conditions=None,
    actions=None,
):
    if conditions is None:
        conditions = [{"field": "description", "operator": "contains", "value": "CVS"}]
    if actions is None:
        actions = [{"action_type": "mark_hsa"}]
    return {
        "name": name,
        "priority": priority,
        "is_active": is_active,
        "conditions": conditions,
        "actions": actions,
    }


def _make_rule(db_session, user_id, name="Test Rule", priority=0, is_active=True):
    now = datetime.utcnow()
    rule = HsaRule(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        priority=priority,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    db_session.add(rule)
    db_session.flush()

    cond = HsaRuleCondition(
        id=uuid.uuid4(),
        rule_id=rule.id,
        field="description",
        operator="contains",
        value="CVS",
        created_at=now,
    )
    db_session.add(cond)

    action = HsaRuleAction(
        id=uuid.uuid4(),
        rule_id=rule.id,
        action_type="mark_hsa",
        created_at=now,
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(rule)
    return rule


def _make_other_user(db_session):
    """Create a second user in the DB so FK constraints pass."""
    now = datetime.utcnow()
    user = User(
        id=uuid.uuid4(),
        username=f"other_{uuid.uuid4().hex[:6]}",
        display_name="Other User",
        email=None,
        hashed_password=None,
        is_active=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_connection(db_session, user_id):
    conn = BankConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="teller",
        provider_account_id=f"acct_{uuid.uuid4().hex[:6]}",
        account_name="HSA Checking",
        account_type="depository",
        account_subtype="hsa",
        institution_name="First National",
        currency="USD",
        enrollment_token="tok_test",
        is_active=True,
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)
    return conn


def _make_transaction(db_session, connection_id, description="CVS Pharmacy", details=None):
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=connection_id,
        provider="teller",
        provider_transaction_id=f"txn_{uuid.uuid4().hex[:6]}",
        transaction_date=datetime(2026, 3, 1).date(),
        description=description,
        amount="-42.00",
        status="posted",
        details=details,
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    return txn


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------


class TestRulesAuthRequired:
    def test_list_rules_requires_auth(self, client):
        assert client.get("/api/v1/bank/rules").status_code == 403

    def test_create_rule_requires_auth(self, client):
        assert client.post("/api/v1/bank/rules", json=_rule_payload()).status_code == 403

    def test_get_rule_requires_auth(self, client):
        assert client.get(f"/api/v1/bank/rules/{uuid.uuid4()}").status_code == 403

    def test_update_rule_requires_auth(self, client):
        assert client.put(f"/api/v1/bank/rules/{uuid.uuid4()}", json=_rule_payload()).status_code == 403

    def test_delete_rule_requires_auth(self, client):
        assert client.delete(f"/api/v1/bank/rules/{uuid.uuid4()}").status_code == 403

    def test_reorder_requires_auth(self, client):
        assert client.patch("/api/v1/bank/rules/reorder", json=[]).status_code == 403

    def test_apply_requires_auth(self, client):
        assert client.post("/api/v1/bank/rules/apply").status_code == 403


# ---------------------------------------------------------------------------
# List rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_returns_empty_list_when_no_rules(self, client, auth_headers):
        resp = client.get("/api/v1/bank/rules", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_rules_for_current_user(self, client, auth_headers, db_session, test_user):
        _make_rule(db_session, test_user.id, name="Rule A")
        _make_rule(db_session, test_user.id, name="Rule B")

        resp = client.get("/api/v1/bank/rules", headers=auth_headers)
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert "Rule A" in names
        assert "Rule B" in names

    def test_does_not_return_other_users_rules(self, client, auth_headers, db_session):
        other_user = _make_other_user(db_session)
        _make_rule(db_session, other_user.id, name="Other User Rule")

        resp = client.get("/api/v1/bank/rules", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_rules_ordered_by_priority(self, client, auth_headers, db_session, test_user):
        _make_rule(db_session, test_user.id, name="High priority", priority=10)
        _make_rule(db_session, test_user.id, name="Low priority", priority=0)

        resp = client.get("/api/v1/bank/rules", headers=auth_headers)
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert names.index("Low priority") < names.index("High priority")

    def test_rule_includes_conditions_and_actions(self, client, auth_headers, db_session, test_user):
        _make_rule(db_session, test_user.id)
        resp = client.get("/api/v1/bank/rules", headers=auth_headers)
        rule = resp.json()[0]
        assert len(rule["conditions"]) == 1
        assert rule["conditions"][0]["field"] == "description"
        assert len(rule["actions"]) == 1
        assert rule["actions"][0]["action_type"] == "mark_hsa"


# ---------------------------------------------------------------------------
# Create rule
# ---------------------------------------------------------------------------


class TestCreateRule:
    def test_creates_rule_with_conditions_and_actions(self, client, auth_headers, db_session):
        resp = client.post(
            "/api/v1/bank/rules",
            json=_rule_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Pharmacy Rule"
        assert len(data["conditions"]) == 1
        assert len(data["actions"]) == 1

    def test_create_rule_persisted_in_db(self, client, auth_headers, db_session, test_user):
        client.post("/api/v1/bank/rules", json=_rule_payload(), headers=auth_headers)
        count = db_session.query(HsaRule).filter(HsaRule.user_id == test_user.id).count()
        assert count == 1

    def test_rejects_empty_conditions(self, client, auth_headers):
        payload = _rule_payload(conditions=[])
        resp = client.post("/api/v1/bank/rules", json=payload, headers=auth_headers)
        assert resp.status_code == 422

    def test_rejects_empty_actions(self, client, auth_headers):
        payload = _rule_payload(actions=[])
        resp = client.post("/api/v1/bank/rules", json=payload, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_with_multiple_conditions(self, client, auth_headers):
        payload = _rule_payload(conditions=[
            {"field": "description", "operator": "contains", "value": "CVS"},
            {"field": "amount", "operator": "lt", "value": "-10"},
        ])
        resp = client.post("/api/v1/bank/rules", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        assert len(resp.json()["conditions"]) == 2

    def test_create_with_assign_member_action(self, client, auth_headers, db_session, test_user_household):
        from app.models.family import FamilyMember
        now = datetime.utcnow()
        member = FamilyMember(
            id=uuid.uuid4(),
            household_id=test_user_household.id,
            name="Jane",
            member_relationship="spouse",
            is_tax_dependent=False,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(member)
        db_session.commit()

        member_id = str(member.id)
        payload = _rule_payload(actions=[
            {"action_type": "assign_member", "member_id": member_id}
        ])
        resp = client.post("/api/v1/bank/rules", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["actions"][0]["member_id"] == member_id


# ---------------------------------------------------------------------------
# Get single rule
# ---------------------------------------------------------------------------


class TestGetRule:
    def test_returns_rule_by_id(self, client, auth_headers, db_session, test_user):
        rule = _make_rule(db_session, test_user.id)
        resp = client.get(f"/api/v1/bank/rules/{rule.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == str(rule.id)

    def test_returns_404_for_unknown_rule(self, client, auth_headers):
        resp = client.get(f"/api/v1/bank/rules/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_404_for_other_users_rule(self, client, auth_headers, db_session):
        other_user = _make_other_user(db_session)
        rule = _make_rule(db_session, other_user.id)
        resp = client.get(f"/api/v1/bank/rules/{rule.id}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update (PUT) rule
# ---------------------------------------------------------------------------


class TestUpdateRule:
    def test_updates_rule_fields(self, client, auth_headers, db_session, test_user):
        rule = _make_rule(db_session, test_user.id, name="Old Name")
        payload = _rule_payload(name="New Name", priority=5)
        resp = client.put(f"/api/v1/bank/rules/{rule.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"
        assert data["priority"] == 5

    def test_replaces_conditions(self, client, auth_headers, db_session, test_user):
        rule = _make_rule(db_session, test_user.id)
        payload = _rule_payload(conditions=[
            {"field": "counterparty_name", "operator": "is", "value": "Walgreens"}
        ])
        resp = client.put(f"/api/v1/bank/rules/{rule.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        conds = resp.json()["conditions"]
        assert len(conds) == 1
        assert conds[0]["field"] == "counterparty_name"

    def test_replaces_actions(self, client, auth_headers, db_session, test_user):
        rule = _make_rule(db_session, test_user.id)
        payload = _rule_payload(actions=[{"action_type": "hide"}])
        resp = client.put(f"/api/v1/bank/rules/{rule.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["actions"][0]["action_type"] == "hide"

    def test_returns_404_for_unknown_rule(self, client, auth_headers):
        resp = client.put(
            f"/api/v1/bank/rules/{uuid.uuid4()}",
            json=_rule_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete rule
# ---------------------------------------------------------------------------


class TestDeleteRule:
    def test_deletes_rule(self, client, auth_headers, db_session, test_user):
        rule = _make_rule(db_session, test_user.id)
        resp = client.delete(f"/api/v1/bank/rules/{rule.id}", headers=auth_headers)
        assert resp.status_code == 204
        assert db_session.query(HsaRule).filter(HsaRule.id == rule.id).first() is None

    def test_returns_404_for_unknown_rule(self, client, auth_headers):
        resp = client.delete(f"/api/v1/bank/rules/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    def test_cannot_delete_other_users_rule(self, client, auth_headers, db_session):
        other_user = _make_other_user(db_session)
        rule = _make_rule(db_session, other_user.id)
        resp = client.delete(f"/api/v1/bank/rules/{rule.id}", headers=auth_headers)
        assert resp.status_code == 404
        # Rule still exists
        assert db_session.query(HsaRule).filter(HsaRule.id == rule.id).first() is not None


# ---------------------------------------------------------------------------
# Reorder rules
# ---------------------------------------------------------------------------


class TestReorderRules:
    def test_reorders_rules(self, client, auth_headers, db_session, test_user):
        rule_a = _make_rule(db_session, test_user.id, name="A", priority=0)
        rule_b = _make_rule(db_session, test_user.id, name="B", priority=1)

        resp = client.patch(
            "/api/v1/bank/rules/reorder",
            json=[
                {"id": str(rule_a.id), "priority": 10},
                {"id": str(rule_b.id), "priority": 0},
            ],
            headers=auth_headers,
        )
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert names.index("B") < names.index("A")

    def test_ignores_other_users_rules_in_reorder(self, client, auth_headers, db_session, test_user):
        other_user = _make_other_user(db_session)
        rule = _make_rule(db_session, other_user.id)
        original_priority = rule.priority

        resp = client.patch(
            "/api/v1/bank/rules/reorder",
            json=[{"id": str(rule.id), "priority": 99}],
            headers=auth_headers,
        )
        assert resp.status_code == 200
        db_session.refresh(rule)
        assert rule.priority == original_priority


# ---------------------------------------------------------------------------
# Apply rules
# ---------------------------------------------------------------------------


class TestApplyRules:
    def test_apply_returns_updated_count(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id, description="CVS Pharmacy")
        _make_rule(db_session, test_user.id)

        resp = client.post("/api/v1/bank/rules/apply", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["updated"] >= 1

    def test_apply_with_no_rules_returns_zero(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id)

        resp = client.post("/api/v1/bank/rules/apply", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0

    def test_apply_with_no_transactions_returns_zero(self, client, auth_headers, db_session, test_user):
        _make_rule(db_session, test_user.id)

        resp = client.post("/api/v1/bank/rules/apply", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0

    def test_apply_marks_transaction_as_hsa(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id, description="CVS Pharmacy")
        _make_rule(db_session, test_user.id)

        client.post("/api/v1/bank/rules/apply", headers=auth_headers)

        db_session.refresh(txn)
        assert txn.is_hsa_eligible is True
        assert txn.rule_id is not None

    def test_apply_does_not_affect_other_users_transactions(self, client, auth_headers, db_session, test_user):
        # Create a rule for test_user but a transaction for another user
        other_user = _make_other_user(db_session)
        conn = _make_connection(db_session, other_user.id)
        txn = _make_transaction(db_session, conn.id, description="CVS Pharmacy")
        _make_rule(db_session, test_user.id)

        client.post("/api/v1/bank/rules/apply", headers=auth_headers)

        db_session.refresh(txn)
        assert txn.is_hsa_eligible is None  # untouched

    def test_apply_also_runs_auto_flag(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(
            db_session, conn.id,
            description="Doctor visit",
            details={"category": "health"},
        )

        resp = client.post("/api/v1/bank/rules/apply", headers=auth_headers)
        assert resp.status_code == 200

        db_session.refresh(txn)
        assert txn.auto_flag == "potential_hsa"


# ---------------------------------------------------------------------------
# show_hidden and auto_flag filter on GET /transactions
# ---------------------------------------------------------------------------


class TestTransactionFilters:
    def test_hidden_transactions_excluded_by_default(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        visible = _make_transaction(db_session, conn.id, description="Visible")
        hidden = _make_transaction(db_session, conn.id, description="Hidden")
        hidden.auto_flag = "hidden"
        db_session.commit()

        resp = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert resp.status_code == 200
        descs = [t["description"] for t in resp.json()]
        assert "Visible" in descs
        assert "Hidden" not in descs

    def test_hidden_transactions_included_when_show_hidden_true(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        hidden = _make_transaction(db_session, conn.id, description="Hidden")
        hidden.auto_flag = "hidden"
        db_session.commit()

        resp = client.get(
            "/api/v1/bank/transactions",
            params={"show_hidden": "true"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        descs = [t["description"] for t in resp.json()]
        assert "Hidden" in descs

    def test_auto_flag_filter(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        potential = _make_transaction(db_session, conn.id, description="Potential")
        potential.auto_flag = "potential_hsa"
        normal = _make_transaction(db_session, conn.id, description="Normal")
        db_session.commit()

        resp = client.get(
            "/api/v1/bank/transactions",
            params={"auto_flag": "potential_hsa"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        descs = [t["description"] for t in resp.json()]
        assert "Potential" in descs
        assert "Normal" not in descs

    def test_transaction_response_includes_auto_flag_and_rule_id(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        rule = _make_rule(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)
        txn.auto_flag = "potential_hsa"
        txn.rule_id = rule.id
        db_session.commit()

        resp = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()[0]
        assert data["auto_flag"] == "potential_hsa"
        assert data["rule_id"] == str(rule.id)


# ---------------------------------------------------------------------------
# Preview rule
# ---------------------------------------------------------------------------


_PREVIEW_PAYLOAD = {
    "rule": {
        "conditions": [{"field": "description", "operator": "contains", "value": "CVS"}],
        "actions": [{"action_type": "mark_hsa"}],
    }
}


class TestPreviewRule:
    def test_preview_requires_auth(self, client):
        assert client.post("/api/v1/bank/rules/preview", json=_PREVIEW_PAYLOAD).status_code == 403

    def test_preview_returns_matching_transactions(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id, description="CVS Pharmacy")
        _make_transaction(db_session, conn.id, description="Starbucks")

        resp = client.post("/api/v1/bank/rules/preview", json=_PREVIEW_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["transactions"][0]["description"] == "CVS Pharmacy"
        assert data["capped"] is False

    def test_preview_returns_zero_when_no_match(self, client, auth_headers, db_session, test_user):
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id, description="Starbucks")

        resp = client.post("/api/v1/bank/rules/preview", json=_PREVIEW_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_preview_respects_priority_placement_last(self, client, auth_headers, db_session, test_user):
        """A higher-priority existing rule claims the transaction; placement=last should miss it."""
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id, description="CVS Pharmacy")
        # Existing rule (priority=0) also matches CVS
        _make_rule(db_session, test_user.id, priority=0)

        payload = {**_PREVIEW_PAYLOAD, "rule": {**_PREVIEW_PAYLOAD["rule"], "placement": "last"}}
        resp = client.post("/api/v1/bank/rules/preview", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        # The higher-priority rule claims the transaction first, so preview count = 0
        assert resp.json()["count"] == 0

    def test_preview_placement_first_wins_over_existing(self, client, auth_headers, db_session, test_user):
        """placement=first should see the transaction even though an existing rule also matches."""
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id, description="CVS Pharmacy")
        _make_rule(db_session, test_user.id, priority=0)

        payload = {**_PREVIEW_PAYLOAD, "rule": {**_PREVIEW_PAYLOAD["rule"], "placement": "first"}}
        resp = client.post("/api/v1/bank/rules/preview", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_preview_excludes_transactions_from_other_users(self, client, auth_headers, db_session, test_user):
        other = _make_other_user(db_session)
        other_conn = _make_connection(db_session, other.id)
        _make_transaction(db_session, other_conn.id, description="CVS Pharmacy")

        resp = client.post("/api/v1/bank/rules/preview", json=_PREVIEW_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_preview_requires_at_least_one_condition(self, client, auth_headers):
        payload = {"rule": {"conditions": [], "actions": [{"action_type": "mark_hsa"}]}}
        resp = client.post("/api/v1/bank/rules/preview", json=payload, headers=auth_headers)
        assert resp.status_code == 422