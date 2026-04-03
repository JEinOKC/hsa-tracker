"""Household endpoints — family group creation, role management, membership."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.household import Household, HouseholdMembership, HouseholdRole
from app.models.user import User
from app.schemas.household import (
    CreateHouseholdRequest,
    HouseholdDetailOut,
    HouseholdMemberOut,
    HouseholdRoleCreate,
    HouseholdRoleOut,
    HouseholdRoleUpdate,
    TransferAdminRequest,
)

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_membership(user_id, db: Session) -> HouseholdMembership | None:
    return db.query(HouseholdMembership).filter(
        HouseholdMembership.user_id == user_id
    ).first()


def _require_membership(user, db: Session) -> HouseholdMembership:
    mem = _get_membership(user.id, db)
    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not a member of any household")
    return mem


def _require_admin(user, db: Session) -> HouseholdMembership:
    mem = _require_membership(user, db)
    if not mem.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return mem


def _reject_admin_name(name: str | None) -> None:
    """Raise 422 if the role name clashes with the reserved 'admin' label."""
    if name and name.strip().lower() == "admin":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'Admin' is a reserved name. Choose a descriptive role name like 'Spouse' or 'Child'.",
        )


def _build_detail(household: Household, db: Session) -> HouseholdDetailOut:
    memberships = db.query(HouseholdMembership).filter(
        HouseholdMembership.household_id == household.id
    ).all()

    members_out = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        members_out.append(HouseholdMemberOut(
            id=m.id,
            household_id=m.household_id,
            user_id=m.user_id,
            username=user.username if user else "",
            display_name=user.display_name if user else "",
            role=HouseholdRoleOut.model_validate(m.role),
            is_admin=m.is_admin,
            joined_at=m.joined_at,
        ))

    roles_out = [HouseholdRoleOut.model_validate(r) for r in household.roles]

    return HouseholdDetailOut(
        household=household,
        roles=roles_out,
        members=members_out,
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=HouseholdDetailOut, status_code=201)
async def create_household(
    request: CreateHouseholdRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new household. The creator becomes the admin. 409 if user already has a household."""
    if _get_membership(current_user.id, db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are already a member of a household")

    household = Household(
        name=request.name,
        created_by_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(household)
    db.flush()

    # Create a default full-access role for the household creator
    admin_role = HouseholdRole(
        household_id=household.id,
        name="Member",
        can_read_transactions=True,
        can_write_transactions=True,
        can_delete_transactions=True,
        can_read_bank_accounts=True,
        can_write_bank_accounts=True,
        can_delete_bank_accounts=True,
        can_read_documents=True,
        can_write_documents=True,
        can_delete_documents=True,
        can_read_family_members=True,
        can_write_family_members=True,
        can_delete_family_members=True,
        created_at=datetime.utcnow(),
    )
    db.add(admin_role)
    db.flush()

    membership = HouseholdMembership(
        household_id=household.id,
        user_id=current_user.id,
        role_id=admin_role.id,
        is_admin=True,
        joined_at=datetime.utcnow(),
    )
    db.add(membership)
    db.commit()
    db.refresh(household)

    return _build_detail(household, db)


@router.get("/mine", response_model=HouseholdDetailOut)
async def get_my_household(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's household. 404 if not in one."""
    mem = _require_membership(current_user, db)
    household = db.query(Household).filter(Household.id == mem.household_id).first()
    return _build_detail(household, db)


@router.post("/mine/roles", response_model=HouseholdRoleOut, status_code=201)
async def create_role(
    request: HouseholdRoleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a household role. Admin only."""
    _reject_admin_name(request.name)
    mem = _require_admin(current_user, db)

    role = HouseholdRole(
        household_id=mem.household_id,
        created_at=datetime.utcnow(),
        **request.model_dump(),
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.put("/mine/roles/{role_id}", response_model=HouseholdRoleOut)
async def update_role(
    role_id: UUID,
    request: HouseholdRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a household role. Admin only."""
    _reject_admin_name(request.name)
    mem = _require_admin(current_user, db)

    role = db.query(HouseholdRole).filter(
        HouseholdRole.id == role_id,
        HouseholdRole.household_id == mem.household_id,
    ).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    for field, value in request.model_dump(exclude_none=True).items():
        setattr(role, field, value)

    db.commit()
    db.refresh(role)
    return role


@router.delete("/mine/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a household role. Admin only. Blocked if any member uses it."""
    mem = _require_admin(current_user, db)

    role = db.query(HouseholdRole).filter(
        HouseholdRole.id == role_id,
        HouseholdRole.household_id == mem.household_id,
    ).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if any(m.is_admin for m in role.memberships):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a role assigned to an admin. Transfer admin to another member first."
        )

    if role.memberships:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a role that is assigned to members"
        )

    db.delete(role)
    db.commit()


@router.delete("/mine/members/{user_id}", status_code=204)
async def remove_member(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a member from the household. Admin only.
    Cannot remove yourself if you are the only admin."""
    mem = _require_admin(current_user, db)

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove yourself. Transfer admin first."
        )

    target = db.query(HouseholdMembership).filter(
        HouseholdMembership.household_id == mem.household_id,
        HouseholdMembership.user_id == user_id,
    ).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    db.delete(target)
    db.commit()


@router.post("/mine/members/{user_id}/transfer-admin", response_model=HouseholdDetailOut)
async def transfer_admin(
    user_id: UUID,
    request: TransferAdminRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transfer admin status to another member.

    If stay_as_role_id is provided, current admin stays in the household with that role.
    If omitted, current admin leaves the household entirely.
    """
    mem = _require_admin(current_user, db)

    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer admin to yourself")

    target = db.query(HouseholdMembership).filter(
        HouseholdMembership.household_id == mem.household_id,
        HouseholdMembership.user_id == user_id,
    ).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Validate stay_as_role if provided
    if request.stay_as_role_id:
        stay_role = db.query(HouseholdRole).filter(
            HouseholdRole.id == request.stay_as_role_id,
            HouseholdRole.household_id == mem.household_id,
        ).first()
        if not stay_role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay-as role not found")

    # Perform the transfer
    target.is_admin = True

    if request.stay_as_role_id:
        mem.is_admin = False
        mem.role_id = request.stay_as_role_id
    else:
        db.delete(mem)

    db.commit()

    household = db.query(Household).filter(Household.id == target.household_id).first()
    db.refresh(household)
    return _build_detail(household, db)
