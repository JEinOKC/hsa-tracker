"""Tests for role-based account access.

Covers:
  - POST /roles — create a role
  - GET /roles — list own roles
  - PUT /roles/{id} — update role; reject non-owner
  - DELETE /roles/{id} — delete role (cascades access)
  - POST /roles/access — grant access by username
  - DELETE /roles/access/{sub_user_id} — revoke access
  - GET /roles/my-access — accounts I have access to
  - Data visibility: shared transactions, bank accounts, family members
  - Permission enforcement: write/delete blocked when role doesn't allow
  - Revoke immediately removes access
"""

import uuid
from datetime import datetime

import pytest

from app.models.access import AccountAccess, AccountRole
from app.models.bank import BankConnection, BankTransaction
from app.models.family import FamilyMember
from app.models.user import User
from app.utils.security import create_access_token


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_user(db_session, username, display_name=None):
    user = User(
        id=uuid.uuid4(),
        username=username,
        display_name=display_name or username.title(),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _auth(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _make_role(db_session, owner_id, name="Spouse", **perms):
    defaults = dict(
        can_read_transactions=True, can_write_transactions=False, can_delete_transactions=False,
        can_read_bank_accounts=True, can_write_bank_accounts=False, can_delete_bank_accounts=False,
        can_read_documents=True, can_write_documents=False, can_delete_documents=False,
        can_read_family_members=True, can_write_family_members=False, can_delete_family_members=False,
    )
    defaults.update(perms)
    role = AccountRole(id=uuid.uuid4(), owner_user_id=owner_id, name=name, created_at=datetime.utcnow(), **defaults)
    db_session.add(role)
    db_session.commit()
    return role


def _grant(db_session, owner_id, sub_user_id, role_id):
    access = AccountAccess(
        id=uuid.uuid4(),
        owner_user_id=owner_id,
        sub_user_id=sub_user_id,
        role_id=role_id,
        granted_at=datetime.utcnow(),
    )
    db_session.add(access)
    db_session.commit()
    return access


def _make_connection(db_session, user_id, name="My HSA"):
    conn = BankConnection(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="teller",
        provider_account_id=f"acct_{uuid.uuid4().hex[:8]}",
        account_name=name,
        account_type="depository",
        account_subtype="hsa",
        institution_name="Test Bank",
        last_four="1234",
        currency="USD",
        is_active=True,
    )
    db_session.add(conn)
    db_session.commit()
    return conn


def _make_transaction(db_session, connection_id):
    from datetime import date
    txn = BankTransaction(
        id=uuid.uuid4(),
        connection_id=connection_id,
        provider="teller",
        provider_transaction_id=f"txn_{uuid.uuid4().hex[:8]}",
        transaction_date=date(2026, 3, 1),
        description="CVS Pharmacy",
        amount="-50.00",
        transaction_type="card_payment",
        status="posted",
    )
    db_session.add(txn)
    db_session.commit()
    return txn


def _make_family_member(db_session, user_id, name="Alice"):
    member = FamilyMember(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        member_relationship="spouse",
        is_active=True,
    )
    db_session.add(member)
    db_session.commit()
    return member


# ── Role CRUD ─────────────────────────────────────────────────────────────────

class TestRoleCrud:
    def test_create_role(self, client, auth_headers):
        resp = client.post("/api/v1/roles", json={"name": "Spouse"}, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Spouse"
        assert data["can_read_transactions"] is True
        assert data["can_write_transactions"] is False

    def test_list_roles_returns_only_own(self, client, auth_headers, db_session, test_user):
        other = _make_user(db_session, "stranger")
        _make_role(db_session, other.id, name="Other Role")
        _make_role(db_session, test_user.id, name="My Role")
        resp = client.get("/api/v1/roles", headers=auth_headers)
        names = [r["name"] for r in resp.json()]
        assert "My Role" in names
        assert "Other Role" not in names

    def test_update_role(self, client, auth_headers, db_session, test_user):
        role = _make_role(db_session, test_user.id, name="Old Name")
        resp = client.put(
            f"/api/v1/roles/{role.id}",
            json={"name": "New Name", "can_write_transactions": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["can_write_transactions"] is True

    def test_update_role_rejects_non_owner(self, client, db_session):
        other = _make_user(db_session, "owner2")
        role = _make_role(db_session, other.id, name="Their Role")
        intruder = _make_user(db_session, "intruder")
        resp = client.put(
            f"/api/v1/roles/{role.id}",
            json={"name": "Hijacked"},
            headers=_auth(intruder),
        )
        assert resp.status_code == 404

    def test_delete_role_cascades_access(self, client, auth_headers, db_session, test_user):
        sub = _make_user(db_session, "subuser1")
        role = _make_role(db_session, test_user.id, name="Deletable")
        _grant(db_session, test_user.id, sub.id, role.id)
        resp = client.delete(f"/api/v1/roles/{role.id}", headers=auth_headers)
        assert resp.status_code == 204
        db_session.expire_all()
        assert db_session.query(AccountAccess).filter_by(role_id=role.id).first() is None


# ── Access management ─────────────────────────────────────────────────────────

class TestAccessManagement:
    def test_grant_access_by_username(self, client, auth_headers, db_session, test_user):
        sub = _make_user(db_session, "grantee")
        role = _make_role(db_session, test_user.id)
        resp = client.post(
            "/api/v1/roles/access",
            json={"username": "grantee", "role_id": str(role.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["sub_username"] == "grantee"

    def test_grant_access_unknown_user_returns_404(self, client, auth_headers, db_session, test_user):
        role = _make_role(db_session, test_user.id)
        resp = client.post(
            "/api/v1/roles/access",
            json={"username": "nobody", "role_id": str(role.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_revoke_access(self, client, auth_headers, db_session, test_user):
        sub = _make_user(db_session, "revokee")
        role = _make_role(db_session, test_user.id)
        _grant(db_session, test_user.id, sub.id, role.id)
        resp = client.delete(f"/api/v1/roles/access/{sub.id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_list_access(self, client, auth_headers, db_session, test_user):
        sub = _make_user(db_session, "viewer")
        role = _make_role(db_session, test_user.id)
        _grant(db_session, test_user.id, sub.id, role.id)
        resp = client.get("/api/v1/roles/access", headers=auth_headers)
        assert resp.status_code == 200
        usernames = [a["sub_username"] for a in resp.json()]
        assert "viewer" in usernames

    def test_my_access(self, client, db_session, test_user):
        owner = _make_user(db_session, "dataowner")
        role = _make_role(db_session, owner.id, name="ReadOnly")
        _grant(db_session, owner.id, test_user.id, role.id)
        resp = client.get("/api/v1/roles/my-access", headers=_auth(test_user))
        assert resp.status_code == 200
        owners = [a["owner_username"] for a in resp.json()]
        assert "dataowner" in owners


# ── Data visibility ───────────────────────────────────────────────────────────

class TestDataVisibility:
    def test_sub_user_sees_shared_transactions(self, client, db_session, test_user):
        sub = _make_user(db_session, "txn_sub")
        role = _make_role(db_session, test_user.id, can_read_transactions=True)
        _grant(db_session, test_user.id, sub.id, role.id)
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)

        resp = client.get("/api/v1/bank/transactions", headers=_auth(sub))
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert str(txn.id) in ids

    def test_sub_user_cannot_read_transactions_without_permission(self, client, db_session, test_user):
        sub = _make_user(db_session, "no_read_sub")
        role = _make_role(db_session, test_user.id, can_read_transactions=False)
        _grant(db_session, test_user.id, sub.id, role.id)
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id)

        resp = client.get("/api/v1/bank/transactions", headers=_auth(sub))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_sub_user_sees_shared_bank_accounts(self, client, db_session, test_user):
        sub = _make_user(db_session, "acct_sub")
        role = _make_role(db_session, test_user.id, can_read_bank_accounts=True)
        _grant(db_session, test_user.id, sub.id, role.id)
        conn = _make_connection(db_session, test_user.id, name="Shared HSA")

        resp = client.get("/api/v1/bank/accounts", headers=_auth(sub))
        assert resp.status_code == 200
        names = [a["account_name"] for a in resp.json()]
        assert "Shared HSA" in names

    def test_shared_accounts_include_owner_display_name(self, client, db_session, test_user):
        sub = _make_user(db_session, "badge_sub")
        role = _make_role(db_session, test_user.id, can_read_bank_accounts=True)
        _grant(db_session, test_user.id, sub.id, role.id)
        _make_connection(db_session, test_user.id)

        resp = client.get("/api/v1/bank/accounts", headers=_auth(sub))
        accounts = resp.json()
        shared = [a for a in accounts if a["owner_display_name"] is not None]
        assert len(shared) > 0
        assert shared[0]["owner_display_name"] == test_user.display_name

    def test_sub_user_sees_shared_family_members(self, client, db_session, test_user):
        sub = _make_user(db_session, "fam_sub")
        role = _make_role(db_session, test_user.id, can_read_family_members=True)
        _grant(db_session, test_user.id, sub.id, role.id)
        _make_family_member(db_session, test_user.id, name="Bob")

        resp = client.get("/api/v1/families/", headers=_auth(sub))
        assert resp.status_code == 200
        names = [m["name"] for m in resp.json()]
        assert "Bob" in names

    def test_revoke_immediately_removes_access(self, client, db_session, test_user):
        sub = _make_user(db_session, "revoke_vis")
        role = _make_role(db_session, test_user.id, can_read_transactions=True)
        access = _grant(db_session, test_user.id, sub.id, role.id)
        conn = _make_connection(db_session, test_user.id)
        _make_transaction(db_session, conn.id)

        # Before revoke: can see
        resp = client.get("/api/v1/bank/transactions", headers=_auth(sub))
        assert len(resp.json()) > 0

        # Revoke
        db_session.delete(access)
        db_session.commit()

        # After revoke: cannot see
        resp = client.get("/api/v1/bank/transactions", headers=_auth(sub))
        assert resp.json() == []


# ── Permission enforcement ────────────────────────────────────────────────────

class TestPermissionEnforcement:
    def test_write_transaction_allowed(self, client, db_session, test_user):
        sub = _make_user(db_session, "write_ok")
        role = _make_role(db_session, test_user.id, can_read_transactions=True, can_write_transactions=True)
        _grant(db_session, test_user.id, sub.id, role.id)
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)

        resp = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"is_hsa_eligible": True},
            headers=_auth(sub),
        )
        assert resp.status_code == 200

    def test_write_transaction_denied_without_permission(self, client, db_session, test_user):
        sub = _make_user(db_session, "write_denied")
        role = _make_role(db_session, test_user.id, can_read_transactions=True, can_write_transactions=False)
        _grant(db_session, test_user.id, sub.id, role.id)
        conn = _make_connection(db_session, test_user.id)
        txn = _make_transaction(db_session, conn.id)

        resp = client.patch(
            f"/api/v1/bank/transactions/{txn.id}",
            json={"is_hsa_eligible": True},
            headers=_auth(sub),
        )
        assert resp.status_code == 403

    def test_delete_bank_account_allowed(self, client, db_session, test_user):
        sub = _make_user(db_session, "del_ok")
        role = _make_role(db_session, test_user.id, can_read_bank_accounts=True, can_delete_bank_accounts=True)
        _grant(db_session, test_user.id, sub.id, role.id)
        conn = _make_connection(db_session, test_user.id)

        resp = client.delete(f"/api/v1/bank/accounts/{conn.id}", headers=_auth(sub))
        assert resp.status_code == 204

    def test_delete_bank_account_denied_without_permission(self, client, db_session, test_user):
        sub = _make_user(db_session, "del_denied")
        role = _make_role(db_session, test_user.id, can_read_bank_accounts=True, can_delete_bank_accounts=False)
        _grant(db_session, test_user.id, sub.id, role.id)
        conn = _make_connection(db_session, test_user.id)

        resp = client.delete(f"/api/v1/bank/accounts/{conn.id}", headers=_auth(sub))
        assert resp.status_code == 403

    def test_write_family_member_allowed(self, client, db_session, test_user):
        sub = _make_user(db_session, "fam_write_ok")
        role = _make_role(db_session, test_user.id, can_read_family_members=True, can_write_family_members=True)
        _grant(db_session, test_user.id, sub.id, role.id)
        member = _make_family_member(db_session, test_user.id, name="Charlie")

        resp = client.put(
            f"/api/v1/families/{member.id}",
            json={"name": "Charlie Updated"},
            headers=_auth(sub),
        )
        assert resp.status_code == 200

    def test_write_family_member_denied_without_permission(self, client, db_session, test_user):
        sub = _make_user(db_session, "fam_write_denied")
        role = _make_role(db_session, test_user.id, can_read_family_members=True, can_write_family_members=False)
        _grant(db_session, test_user.id, sub.id, role.id)
        member = _make_family_member(db_session, test_user.id, name="Diana")

        resp = client.put(
            f"/api/v1/families/{member.id}",
            json={"name": "Diana Blocked"},
            headers=_auth(sub),
        )
        assert resp.status_code == 404  # Returns 404 (not 403) to avoid info leakage
