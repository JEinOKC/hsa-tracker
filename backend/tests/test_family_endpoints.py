"""Integration tests for family member and HSA eligibility period endpoints."""

import uuid
from datetime import date

import pytest

from app.models.family import FamilyMember, HsaEligibilityPeriod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def member(db_session, test_user):
    """A single active family member owned by test_user."""
    m = FamilyMember(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Jane Doe",
        member_relationship="spouse",
        date_of_birth=date(1985, 6, 15),
        is_tax_dependent=False,
        is_active=True,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def member_with_eligibility(db_session, member):
    """member with one open-ended eligibility period starting 2024-01-01."""
    period = HsaEligibilityPeriod(
        id=uuid.uuid4(),
        family_member_id=member.id,
        start_date=date(2024, 1, 1),
        end_date=None,
    )
    db_session.add(period)
    db_session.commit()
    db_session.refresh(member)
    return member


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestFamilyAuthRequired:
    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/families/").status_code == 403

    def test_create_requires_auth(self, client):
        assert client.post("/api/v1/families/", json={"name": "X", "member_relationship": "self"}).status_code == 403

    def test_get_requires_auth(self, client):
        assert client.get(f"/api/v1/families/{uuid.uuid4()}").status_code == 403

    def test_eligibility_requires_auth(self, client):
        assert client.get(f"/api/v1/families/{uuid.uuid4()}/eligibility").status_code == 403


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestCreateFamilyMember:
    def test_creates_member(self, client, auth_headers, db_session, test_user):
        resp = client.post(
            "/api/v1/families/",
            json={"name": "Alice", "member_relationship": "child"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Alice"
        assert data["member_relationship"] == "child"
        assert data["is_active"] is True
        assert data["is_tax_dependent"] is False
        assert data["user_id"] == str(test_user.id)

    def test_creates_with_eligibility_period(self, client, auth_headers):
        resp = client.post(
            "/api/v1/families/",
            json={
                "name": "Bob",
                "member_relationship": "self",
                "eligibility_start": "2024-01-01",
                "eligibility_end": None,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["eligibility_periods"]) == 1
        assert data["eligibility_periods"][0]["start_date"] == "2024-01-01"
        assert data["eligibility_periods"][0]["end_date"] is None

    def test_creates_with_date_of_birth(self, client, auth_headers):
        resp = client.post(
            "/api/v1/families/",
            json={"name": "Carol", "member_relationship": "child", "date_of_birth": "2010-03-20"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["date_of_birth"] == "2010-03-20"

    def test_invalid_relationship_returns_422(self, client, auth_headers):
        resp = client.post(
            "/api/v1/families/",
            json={"name": "X", "member_relationship": "cousin"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "member_relationship" in resp.json()["detail"].lower()

    def test_missing_name_returns_422(self, client, auth_headers):
        resp = client.post(
            "/api/v1/families/",
            json={"member_relationship": "self"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_all_valid_relationships_accepted(self, client, auth_headers):
        for rel in ("self", "spouse", "child", "other"):
            resp = client.post(
                "/api/v1/families/",
                json={"name": f"Person {rel}", "member_relationship": rel},
                headers=auth_headers,
            )
            assert resp.status_code == 201, f"Expected 201 for relationship={rel}"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListFamilyMembers:
    def test_returns_empty_for_new_user(self, client, auth_headers):
        resp = client.get("/api/v1/families/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_user_members(self, client, auth_headers, member):
        resp = client.get("/api/v1/families/", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["id"] == str(member.id)

    def test_excludes_inactive_by_default(self, client, auth_headers, db_session, test_user):
        inactive = FamilyMember(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name="Inactive",
            member_relationship="other",
            is_active=False,
        )
        db_session.add(inactive)
        db_session.commit()

        resp = client.get("/api/v1/families/", headers=auth_headers)
        ids = [m["id"] for m in resp.json()]
        assert str(inactive.id) not in ids

    def test_includes_inactive_when_requested(self, client, auth_headers, db_session, test_user, member):
        inactive = FamilyMember(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name="Inactive",
            member_relationship="other",
            is_active=False,
        )
        db_session.add(inactive)
        db_session.commit()

        resp = client.get("/api/v1/families/?include_inactive=true", headers=auth_headers)
        ids = [m["id"] for m in resp.json()]
        assert str(inactive.id) in ids
        assert str(member.id) in ids

    def test_does_not_return_other_users_members(self, client, auth_headers, db_session):
        other_user_id = uuid.uuid4()
        other_member = FamilyMember(
            id=uuid.uuid4(),
            user_id=other_user_id,
            name="Someone Else",
            member_relationship="self",
            is_active=True,
        )
        db_session.add(other_member)
        db_session.commit()

        resp = client.get("/api/v1/families/", headers=auth_headers)
        ids = [m["id"] for m in resp.json()]
        assert str(other_member.id) not in ids


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------

class TestGetFamilyMember:
    def test_returns_member(self, client, auth_headers, member):
        resp = client.get(f"/api/v1/families/{member.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == str(member.id)
        assert resp.json()["name"] == "Jane Doe"

    def test_returns_404_for_unknown_id(self, client, auth_headers):
        resp = client.get(f"/api/v1/families/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_404_for_other_users_member(self, client, auth_headers, db_session):
        other = FamilyMember(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Not Mine",
            member_relationship="self",
            is_active=True,
        )
        db_session.add(other)
        db_session.commit()

        resp = client.get(f"/api/v1/families/{other.id}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestUpdateFamilyMember:
    def test_updates_name(self, client, auth_headers, member):
        resp = client.put(
            f"/api/v1/families/{member.id}",
            json={"name": "Jane Smith"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Jane Smith"

    def test_updates_tax_dependent(self, client, auth_headers, member):
        resp = client.put(
            f"/api/v1/families/{member.id}",
            json={"is_tax_dependent": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_tax_dependent"] is True

    def test_invalid_relationship_returns_422(self, client, auth_headers, member):
        resp = client.put(
            f"/api/v1/families/{member.id}",
            json={"member_relationship": "aunt"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_returns_404_for_unknown(self, client, auth_headers):
        resp = client.put(
            f"/api/v1/families/{uuid.uuid4()}",
            json={"name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Deactivate
# ---------------------------------------------------------------------------

class TestDeactivateFamilyMember:
    def test_deactivates_member(self, client, auth_headers, member, db_session):
        resp = client.delete(f"/api/v1/families/{member.id}", headers=auth_headers)
        assert resp.status_code == 204

        db_session.refresh(member)
        assert member.is_active is False

    def test_deactivated_member_hidden_from_list(self, client, auth_headers, member):
        client.delete(f"/api/v1/families/{member.id}", headers=auth_headers)
        resp = client.get("/api/v1/families/", headers=auth_headers)
        ids = [m["id"] for m in resp.json()]
        assert str(member.id) not in ids

    def test_returns_404_for_unknown(self, client, auth_headers):
        assert client.delete(f"/api/v1/families/{uuid.uuid4()}", headers=auth_headers).status_code == 404


# ---------------------------------------------------------------------------
# Eligibility periods
# ---------------------------------------------------------------------------

class TestEligibilityPeriods:
    def test_add_open_ended_period(self, client, auth_headers, member):
        resp = client.post(
            f"/api/v1/families/{member.id}/eligibility",
            json={"start_date": "2024-01-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["start_date"] == "2024-01-01"
        assert data["end_date"] is None

    def test_add_closed_period(self, client, auth_headers, member):
        resp = client.post(
            f"/api/v1/families/{member.id}/eligibility",
            json={"start_date": "2023-01-01", "end_date": "2023-12-31", "notes": "HDHP year"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["start_date"] == "2023-01-01"
        assert data["end_date"] == "2023-12-31"
        assert data["notes"] == "HDHP year"

    def test_end_before_start_returns_422(self, client, auth_headers, member):
        resp = client.post(
            f"/api/v1/families/{member.id}/eligibility",
            json={"start_date": "2024-06-01", "end_date": "2024-01-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_list_periods(self, client, auth_headers, member_with_eligibility):
        resp = client.get(
            f"/api/v1/families/{member_with_eligibility.id}/eligibility",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_period(self, client, auth_headers, member_with_eligibility, db_session):
        period_id = member_with_eligibility.eligibility_periods[0].id
        resp = client.delete(
            f"/api/v1/families/{member_with_eligibility.id}/eligibility/{period_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        remaining = db_session.query(HsaEligibilityPeriod).filter(
            HsaEligibilityPeriod.family_member_id == member_with_eligibility.id
        ).all()
        assert len(remaining) == 0

    def test_update_period_end_date(self, client, auth_headers, member_with_eligibility):
        period_id = member_with_eligibility.eligibility_periods[0].id
        resp = client.put(
            f"/api/v1/families/{member_with_eligibility.id}/eligibility/{period_id}",
            json={"end_date": "2025-12-31"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["end_date"] == "2025-12-31"

    def test_period_404_for_unknown_member(self, client, auth_headers):
        resp = client.get(
            f"/api/v1/families/{uuid.uuid4()}/eligibility",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Eligibility check
# ---------------------------------------------------------------------------

class TestEligibilityCheck:
    def test_eligible_on_date_within_period(self, client, auth_headers, member_with_eligibility):
        resp = client.get(
            f"/api/v1/families/{member_with_eligibility.id}/eligibility/check",
            params={"expense_date": "2025-03-15"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_eligible"] is True
        assert data["matched_period"] is not None

    def test_not_eligible_before_period(self, client, auth_headers, member_with_eligibility):
        resp = client.get(
            f"/api/v1/families/{member_with_eligibility.id}/eligibility/check",
            params={"expense_date": "2023-12-31"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_eligible"] is False
        assert data["matched_period"] is None

    def test_not_eligible_with_no_periods(self, client, auth_headers, member):
        resp = client.get(
            f"/api/v1/families/{member.id}/eligibility/check",
            params={"expense_date": "2025-01-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_eligible"] is False

    def test_closed_period_eligible_on_last_day(self, client, auth_headers, member, db_session):
        period = HsaEligibilityPeriod(
            id=uuid.uuid4(),
            family_member_id=member.id,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        db_session.add(period)
        db_session.commit()

        resp = client.get(
            f"/api/v1/families/{member.id}/eligibility/check",
            params={"expense_date": "2023-12-31"},
            headers=auth_headers,
        )
        assert resp.json()["is_eligible"] is True

    def test_closed_period_not_eligible_day_after(self, client, auth_headers, member, db_session):
        period = HsaEligibilityPeriod(
            id=uuid.uuid4(),
            family_member_id=member.id,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        db_session.add(period)
        db_session.commit()

        resp = client.get(
            f"/api/v1/families/{member.id}/eligibility/check",
            params={"expense_date": "2024-01-01"},
            headers=auth_headers,
        )
        assert resp.json()["is_eligible"] is False

    def test_member_response_includes_eligibility_periods(self, client, auth_headers, member_with_eligibility):
        resp = client.get(f"/api/v1/families/{member_with_eligibility.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["eligibility_periods"]) == 1
