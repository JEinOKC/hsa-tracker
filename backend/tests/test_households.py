"""Tests for the household endpoints and permission paths.

  POST   /households                                     - create household
  GET    /households/mine                                - get my household
  POST   /households/mine/roles                          - create role
  PUT    /households/mine/roles/{id}                     - update role
  DELETE /households/mine/roles/{id}                     - delete role
  DELETE /households/mine/members/{user_id}              - remove member
  POST   /households/mine/members/{user_id}/transfer-admin - transfer admin
"""

import uuid
from datetime import date, datetime

from app.models.household import Household, HouseholdMembership, HouseholdRole
from app.models.user import User


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_user(db, username="otheruser"):
    user = User(
        id=uuid.uuid4(),
        username=username,
        display_name=username.title(),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _make_household(db, creator_id, name="Test Family"):
    h = Household(id=uuid.uuid4(), name=name, created_by_id=creator_id, created_at=datetime.utcnow())
    db.add(h)
    db.flush()
    return h


def _make_role(db, household_id, name="Member", **perms):
    defaults = dict(
        can_read_transactions=True, can_write_transactions=False, can_delete_transactions=False,
        can_read_bank_accounts=True, can_write_bank_accounts=False, can_delete_bank_accounts=False,
        can_read_documents=True, can_write_documents=False, can_delete_documents=False,
        can_read_family_members=True, can_write_family_members=False, can_delete_family_members=False,
    )
    defaults.update(perms)
    r = HouseholdRole(id=uuid.uuid4(), household_id=household_id, name=name, created_at=datetime.utcnow(), **defaults)
    db.add(r)
    db.flush()
    return r


def _make_membership(db, household_id, user_id, role_id, is_admin=False):
    m = HouseholdMembership(
        id=uuid.uuid4(),
        household_id=household_id,
        user_id=user_id,
        role_id=role_id,
        is_admin=is_admin,
        joined_at=datetime.utcnow(),
    )
    db.add(m)
    db.flush()
    return m


def _setup_household_with_admin(db, test_user):
    """Create household + admin role + admin membership for test_user."""
    h = _make_household(db, test_user.id)
    admin_role = _make_role(db, h.id, name="Admin",
        can_write_transactions=True, can_delete_transactions=True,
        can_write_bank_accounts=True, can_delete_bank_accounts=True,
        can_write_documents=True, can_delete_documents=True,
        can_write_family_members=True, can_delete_family_members=True,
    )
    _make_membership(db, h.id, test_user.id, admin_role.id, is_admin=True)
    db.commit()
    return h, admin_role


# ── create household ──────────────────────────────────────────────────────────

class TestCreateHousehold:
    def test_creates_household(self, client, db_session, test_user, auth_headers):
        r = client.post("/api/v1/households", json={"name": "England Family"}, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["household"]["name"] == "England Family"
        assert len(data["members"]) == 1
        assert data["members"][0]["is_admin"] is True
        assert data["members"][0]["user_id"] == str(test_user.id)

    def test_creates_default_admin_role(self, client, db_session, test_user, auth_headers):
        r = client.post("/api/v1/households", json={"name": "My Household"}, headers=auth_headers)
        assert r.status_code == 201
        roles = r.json()["roles"]
        assert len(roles) == 1
        assert roles[0]["name"] == "Member"
        assert roles[0]["can_write_transactions"] is True

    def test_409_if_already_in_household(self, client, db_session, test_user, auth_headers):
        _setup_household_with_admin(db_session, test_user)
        r = client.post("/api/v1/households", json={"name": "Another"}, headers=auth_headers)
        assert r.status_code == 409

    def test_requires_auth(self, client):
        r = client.post("/api/v1/households", json={"name": "X"})
        assert r.status_code == 403


# ── get my household ──────────────────────────────────────────────────────────

class TestGetMyHousehold:
    def test_returns_household(self, client, db_session, test_user, auth_headers):
        h, _ = _setup_household_with_admin(db_session, test_user)
        r = client.get("/api/v1/households/mine", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["household"]["id"] == str(h.id)

    def test_404_if_not_member(self, client, auth_headers):
        r = client.get("/api/v1/households/mine", headers=auth_headers)
        assert r.status_code == 404


# ── role CRUD ─────────────────────────────────────────────────────────────────

class TestHouseholdRoles:
    def test_admin_can_create_role(self, client, db_session, test_user, auth_headers):
        _setup_household_with_admin(db_session, test_user)
        r = client.post(
            "/api/v1/households/mine/roles",
            json={"name": "Spouse", "can_write_transactions": True},
            headers=auth_headers,
        )
        assert r.status_code == 201
        assert r.json()["name"] == "Spouse"
        assert r.json()["can_write_transactions"] is True

    def test_cannot_create_role_named_admin(self, client, db_session, test_user, auth_headers):
        _setup_household_with_admin(db_session, test_user)
        r = client.post(
            "/api/v1/households/mine/roles",
            json={"name": "Admin"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_cannot_update_role_to_admin_name(self, client, db_session, test_user, auth_headers):
        h, admin_role = _setup_household_with_admin(db_session, test_user)
        r = client.put(
            f"/api/v1/households/mine/roles/{admin_role.id}",
            json={"name": "Admin"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_non_admin_cannot_create_role(self, client, db_session, test_user, auth_headers):
        h = _make_household(db_session, test_user.id)
        member_role = _make_role(db_session, h.id, name="Member")
        _make_membership(db_session, h.id, test_user.id, member_role.id, is_admin=False)
        db_session.commit()

        r = client.post(
            "/api/v1/households/mine/roles",
            json={"name": "NewRole"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_admin_can_update_role(self, client, db_session, test_user, auth_headers):
        h, admin_role = _setup_household_with_admin(db_session, test_user)
        r = client.put(
            f"/api/v1/households/mine/roles/{admin_role.id}",
            json={"name": "Owner"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Owner"

    def test_admin_can_delete_unused_role(self, client, db_session, test_user, auth_headers):
        h, admin_role = _setup_household_with_admin(db_session, test_user)
        unused = _make_role(db_session, h.id, name="Unused")
        db_session.commit()

        r = client.delete(f"/api/v1/households/mine/roles/{unused.id}", headers=auth_headers)
        assert r.status_code == 204

    def test_cannot_delete_role_in_use(self, client, db_session, test_user, auth_headers):
        # admin_role is in use by test_user's membership
        h, admin_role = _setup_household_with_admin(db_session, test_user)
        r = client.delete(f"/api/v1/households/mine/roles/{admin_role.id}", headers=auth_headers)
        assert r.status_code == 409

    def test_cannot_delete_role_assigned_to_admin(self, client, db_session, test_user, auth_headers):
        h, admin_role = _setup_household_with_admin(db_session, test_user)
        r = client.delete(f"/api/v1/households/mine/roles/{admin_role.id}", headers=auth_headers)
        assert r.status_code == 409
        assert "admin" in r.json()["detail"].lower()


# ── remove member ─────────────────────────────────────────────────────────────

class TestRemoveMember:
    def test_admin_can_remove_member(self, client, db_session, test_user, auth_headers):
        h, admin_role = _setup_household_with_admin(db_session, test_user)
        other = _make_user(db_session, "other_remove")
        member_role = _make_role(db_session, h.id, name="Member")
        _make_membership(db_session, h.id, other.id, member_role.id, is_admin=False)
        db_session.commit()

        r = client.delete(f"/api/v1/households/mine/members/{other.id}", headers=auth_headers)
        assert r.status_code == 204

        remaining = db_session.query(HouseholdMembership).filter(
            HouseholdMembership.household_id == h.id
        ).all()
        assert all(m.user_id != other.id for m in remaining)

    def test_admin_cannot_remove_self(self, client, db_session, test_user, auth_headers):
        _setup_household_with_admin(db_session, test_user)
        r = client.delete(f"/api/v1/households/mine/members/{test_user.id}", headers=auth_headers)
        assert r.status_code == 409

    def test_non_admin_cannot_remove_member(self, client, db_session, test_user, auth_headers):
        h = _make_household(db_session, test_user.id)
        role = _make_role(db_session, h.id, name="Member")
        _make_membership(db_session, h.id, test_user.id, role.id, is_admin=False)
        other = _make_user(db_session, "other_noremove")
        _make_membership(db_session, h.id, other.id, role.id, is_admin=False)
        db_session.commit()

        r = client.delete(f"/api/v1/households/mine/members/{other.id}", headers=auth_headers)
        assert r.status_code == 403


# ── transfer admin ────────────────────────────────────────────────────────────

class TestTransferAdmin:
    def test_transfer_and_leave(self, client, db_session, test_user, auth_headers):
        h, admin_role = _setup_household_with_admin(db_session, test_user)
        other = _make_user(db_session, "other_transfer1")
        member_role = _make_role(db_session, h.id, name="Member")
        _make_membership(db_session, h.id, other.id, member_role.id, is_admin=False)
        db_session.commit()

        # Transfer without stay_as_role_id → admin leaves
        r = client.post(
            f"/api/v1/households/mine/members/{other.id}/transfer-admin",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 200
        members = r.json()["members"]
        other_data = next(m for m in members if m["user_id"] == str(other.id))
        assert other_data["is_admin"] is True
        # test_user should no longer be in members
        assert all(m["user_id"] != str(test_user.id) for m in members)

    def test_transfer_and_stay_with_role(self, client, db_session, test_user, auth_headers):
        h, admin_role = _setup_household_with_admin(db_session, test_user)
        other = _make_user(db_session, "other_transfer2")
        member_role = _make_role(db_session, h.id, name="Member")
        _make_membership(db_session, h.id, other.id, member_role.id, is_admin=False)
        db_session.commit()

        r = client.post(
            f"/api/v1/households/mine/members/{other.id}/transfer-admin",
            json={"stay_as_role_id": str(member_role.id)},
            headers=auth_headers,
        )
        assert r.status_code == 200
        members = r.json()["members"]
        other_data = next(m for m in members if m["user_id"] == str(other.id))
        assert other_data["is_admin"] is True
        me_data = next(m for m in members if m["user_id"] == str(test_user.id))
        assert me_data["is_admin"] is False
        assert me_data["role"]["id"] == str(member_role.id)

    def test_cannot_transfer_to_self(self, client, db_session, test_user, auth_headers):
        _setup_household_with_admin(db_session, test_user)
        r = client.post(
            f"/api/v1/households/mine/members/{test_user.id}/transfer-admin",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 400


# ── household permission path ─────────────────────────────────────────────────

class TestHouseholdPermissions:
    def test_member_can_read_other_members_transactions(self, client, db_session, test_user, auth_headers):
        from app.models.bank import BankConnection, BankTransaction
        from decimal import Decimal

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        other = _make_user(db_session, "other_txn_perm")
        member_role = _make_role(db_session, h.id, name="Spouse",
            can_read_transactions=True, can_write_transactions=True,
        )
        _make_membership(db_session, h.id, other.id, member_role.id, is_admin=False)

        # Create a connection + transaction owned by `other`
        conn = BankConnection(
            id=uuid.uuid4(),
            user_id=other.id,
            provider="teller",
            provider_account_id="other_acct",
            account_name="Other Bank",
            institution_name="Acme",
            currency="USD",
            is_active=True,
        )
        db_session.add(conn)
        db_session.flush()
        txn = BankTransaction(
            id=uuid.uuid4(),
            connection_id=conn.id,
            provider="teller",
            provider_transaction_id="other_txn",
            transaction_date=date(2026, 1, 1),
            description="Other User Purchase",
            amount=Decimal("-20.00"),
            status="posted",
        )
        db_session.add(txn)
        db_session.commit()

        # test_user (admin) should see other's transactions
        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert r.status_code == 200
        descriptions = [t["description"] for t in r.json()]
        assert "Other User Purchase" in descriptions

    def test_removed_member_loses_access(self, client, db_session, test_user, auth_headers):
        from app.models.bank import BankConnection, BankTransaction
        from decimal import Decimal

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        other = _make_user(db_session, "other_removed_perm")
        member_role = _make_role(db_session, h.id, name="Member")
        mem = _make_membership(db_session, h.id, other.id, member_role.id, is_admin=False)

        conn = BankConnection(
            id=uuid.uuid4(),
            user_id=other.id,
            provider="teller",
            provider_account_id="removed_acct",
            account_name="Removed Bank",
            institution_name="Acme",
            currency="USD",
            is_active=True,
        )
        db_session.add(conn)
        db_session.flush()
        txn = BankTransaction(
            id=uuid.uuid4(),
            connection_id=conn.id,
            provider="teller",
            provider_transaction_id="removed_txn",
            transaction_date=date(2026, 1, 1),
            description="Should Disappear",
            amount=Decimal("-10.00"),
            status="posted",
        )
        db_session.add(txn)
        db_session.commit()

        # Verify visible before removal
        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert any(t["description"] == "Should Disappear" for t in r.json())

        # Remove the member
        db_session.delete(mem)
        db_session.commit()

        # Should no longer be visible
        r = client.get("/api/v1/bank/transactions", headers=auth_headers)
        assert all(t["description"] != "Should Disappear" for t in r.json())


# ── family member auto-creation on household join ─────────────────────────────

class TestHouseholdJoinCreatesFamilyMembers:
    def _simulate_household_join(self, db, household_id, role_id, new_user, family_member_id=None):
        """Replicate the logic from passkey_register_complete for a household invite."""
        from app.models.family import FamilyMember
        from app.models.household import HouseholdMembership, HouseholdRole

        db.add(HouseholdMembership(
            household_id=household_id,
            user_id=new_user.id,
            role_id=role_id,
            is_admin=False,
            joined_at=datetime.utcnow(),
        ))
        db.flush()

        _valid_rels = {"spouse", "child", "other"}
        new_role = db.query(HouseholdRole).filter(HouseholdRole.id == role_id).first()
        new_user_rel = new_role.name.lower() if new_role and new_role.name.lower() in _valid_rels else "other"

        existing_memberships = db.query(HouseholdMembership).filter(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id != new_user.id,
        ).all()

        for mem in existing_memberships:
            existing_user = db.query(User).filter(User.id == mem.user_id).first()
            if not existing_user:
                continue
            linked_exists = (
                family_member_id is not None
                and db.query(FamilyMember).filter(
                    FamilyMember.id == family_member_id,
                    FamilyMember.user_id == mem.user_id,
                ).first() is not None
            )
            if not linked_exists:
                db.add(FamilyMember(
                    user_id=mem.user_id,
                    name=new_user.display_name,
                    member_relationship=new_user_rel,
                    linked_user_id=new_user.id,
                    is_active=True,
                ))
            existing_role = db.query(HouseholdRole).filter(HouseholdRole.id == mem.role_id).first()
            existing_rel = existing_role.name.lower() if existing_role and existing_role.name.lower() in _valid_rels else "other"
            db.add(FamilyMember(
                user_id=new_user.id,
                name=existing_user.display_name,
                member_relationship=existing_rel,
                linked_user_id=existing_user.id,
                is_active=True,
            ))
        db.commit()

    def test_new_member_appears_in_existing_members_family_list(self, client, db_session, test_user, auth_headers):
        from app.models.family import FamilyMember

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        spouse_role = _make_role(db_session, h.id, name="Spouse")
        db_session.commit()

        jenny = _make_user(db_session, "jenny_fam")
        self._simulate_household_join(db_session, h.id, spouse_role.id, jenny)

        # test_user should now have Jenny in their family list
        members = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == test_user.id
        ).all()
        assert any(m.name == jenny.display_name for m in members)
        jenny_record = next(m for m in members if m.name == jenny.display_name)
        assert jenny_record.member_relationship == "spouse"

    def test_new_member_gets_existing_members_in_their_family_list(self, client, db_session, test_user, auth_headers):
        from app.models.family import FamilyMember

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        spouse_role = _make_role(db_session, h.id, name="Spouse")
        db_session.commit()

        jenny = _make_user(db_session, "jenny_fam2")
        self._simulate_household_join(db_session, h.id, spouse_role.id, jenny)

        # Jenny should have test_user in her family list
        members = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == jenny.id
        ).all()
        assert any(m.name == test_user.display_name for m in members)

    def test_role_name_used_for_relationship(self, client, db_session, test_user, auth_headers):
        from app.models.family import FamilyMember

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        child_role = _make_role(db_session, h.id, name="Child")
        db_session.commit()

        kid = _make_user(db_session, "kid_fam")
        self._simulate_household_join(db_session, h.id, child_role.id, kid)

        record = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == test_user.id,
            FamilyMember.name == kid.display_name,
        ).first()
        assert record.member_relationship == "child"

    def test_unrecognised_role_name_defaults_to_other(self, client, db_session, test_user, auth_headers):
        from app.models.family import FamilyMember

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        custom_role = _make_role(db_session, h.id, name="Roommate")
        db_session.commit()

        roomie = _make_user(db_session, "roomie_fam")
        self._simulate_household_join(db_session, h.id, custom_role.id, roomie)

        record = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == test_user.id,
            FamilyMember.name == roomie.display_name,
        ).first()
        assert record.member_relationship == "other"

    def test_linked_family_member_not_duplicated(self, client, db_session, test_user, auth_headers):
        """When family_member_id is set on the invite, no duplicate FamilyMember is created."""
        from app.models.family import FamilyMember

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        spouse_role = _make_role(db_session, h.id, name="Spouse")
        db_session.commit()

        # Pre-create a FamilyMember record for Jenny in test_user's list
        jenny = _make_user(db_session, "jenny_linked")
        pre_existing = FamilyMember(
            user_id=test_user.id,
            name=jenny.display_name,
            member_relationship="spouse",
            is_active=True,
        )
        db_session.add(pre_existing)
        db_session.commit()
        db_session.refresh(pre_existing)

        # Simulate Jenny joining via invite that references the pre-existing record
        self._simulate_household_join(db_session, h.id, spouse_role.id, jenny, family_member_id=pre_existing.id)

        # test_user should still have exactly one FamilyMember record for Jenny
        jenny_records = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == test_user.id,
            FamilyMember.name == jenny.display_name,
        ).all()
        assert len(jenny_records) == 1

    def test_linked_family_member_other_members_still_get_record(self, client, db_session, test_user, auth_headers):
        """When family_member_id avoids a duplicate for one member, other household members still get a new record."""
        from app.models.family import FamilyMember

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        spouse_role = _make_role(db_session, h.id, name="Spouse")
        db_session.commit()

        # Add a second existing member (alice) to the household
        alice = _make_user(db_session, "alice_linked")
        alice_role = _make_role(db_session, h.id, name="Child")
        db_session.add(HouseholdMembership(
            household_id=h.id,
            user_id=alice.id,
            role_id=alice_role.id,
            is_admin=False,
            joined_at=datetime.utcnow(),
        ))
        db_session.commit()

        # Pre-create Jenny in test_user's list (but NOT in alice's list)
        jenny = _make_user(db_session, "jenny_linked2")
        pre_existing = FamilyMember(
            user_id=test_user.id,
            name=jenny.display_name,
            member_relationship="spouse",
            is_active=True,
        )
        db_session.add(pre_existing)
        db_session.commit()
        db_session.refresh(pre_existing)

        self._simulate_household_join(db_session, h.id, spouse_role.id, jenny, family_member_id=pre_existing.id)

        # test_user: no new duplicate
        jenny_for_test_user = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == test_user.id,
            FamilyMember.name == jenny.display_name,
        ).all()
        assert len(jenny_for_test_user) == 1

        # alice: should have received a new record for Jenny
        jenny_for_alice = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == alice.id,
            FamilyMember.name == jenny.display_name,
        ).all()
        assert len(jenny_for_alice) == 1

    def test_linked_user_id_set_on_both_sides(self, client, db_session, test_user, auth_headers):
        """Both the new user's records for existing members AND existing members' records
        for the new user should have linked_user_id populated after household join."""
        from app.models.family import FamilyMember

        h, admin_role = _setup_household_with_admin(db_session, test_user)
        spouse_role = _make_role(db_session, h.id, name="Spouse")
        db_session.commit()

        jenny = _make_user(db_session, "jenny_link")
        self._simulate_household_join(db_session, h.id, spouse_role.id, jenny)

        # test_user's record for jenny should have linked_user_id = jenny.id
        jenny_record = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == test_user.id,
            FamilyMember.linked_user_id == jenny.id,
        ).first()
        assert jenny_record is not None

        # jenny's record for test_user should have linked_user_id = test_user.id
        test_user_record = db_session.query(FamilyMember).filter(
            FamilyMember.user_id == jenny.id,
            FamilyMember.linked_user_id == test_user.id,
        ).first()
        assert test_user_record is not None
