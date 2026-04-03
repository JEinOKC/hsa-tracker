# TODO(bilateral-roles): This entire module is intentionally dormant.
# The bilateral AccountRole/AccountAccess system allows one user to grant
# another user (e.g. an accountant or advisor) scoped read/write access
# to their account without joining the family household.
# The router is registered in router.py but no frontend UI exposes it yet.
# Re-enable by adding an "External Access" section to the Family Members page
# once the household flow is stable.
"""Role-based account access endpoints"""

import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.access import AccountRole, AccountAccess
from app.schemas.access import (
    AccountRoleCreate,
    AccountRoleUpdate,
    AccountRoleResponse,
    AccessGrantRequest,
    AccessResponse,
    MyAccessResponse,
)
from app.dependencies import get_current_user

router = APIRouter()


def _get_role_or_404(role_id: uuid.UUID, owner_id: uuid.UUID, db: Session) -> AccountRole:
    role = db.query(AccountRole).filter(
        AccountRole.id == role_id,
        AccountRole.owner_user_id == owner_id,
    ).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


# ── Role CRUD (owner perspective) ─────────────────────────────────────────────

@router.get("", response_model=List[AccountRoleResponse])
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all roles the current user has defined."""
    return db.query(AccountRole).filter(AccountRole.owner_user_id == current_user.id).all()


@router.post("", response_model=AccountRoleResponse, status_code=201)
async def create_role(
    request: AccountRoleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new role."""
    role = AccountRole(
        owner_user_id=current_user.id,
        created_at=datetime.utcnow(),
        **request.model_dump(),
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.put("/{role_id}", response_model=AccountRoleResponse)
async def update_role(
    role_id: uuid.UUID,
    request: AccountRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a role. Must be the owner."""
    role = _get_role_or_404(role_id, current_user.id, db)
    for field, value in request.model_dump().items():
        setattr(role, field, value)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a role (cascades to any access grants using this role)."""
    role = _get_role_or_404(role_id, current_user.id, db)
    db.delete(role)
    db.commit()


# ── Access grants (owner perspective) ─────────────────────────────────────────

@router.get("/access", response_model=List[AccessResponse])
async def list_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all users who have access to the current user's account."""
    accesses = (
        db.query(AccountAccess)
        .filter(AccountAccess.owner_user_id == current_user.id)
        .all()
    )
    result = []
    for a in accesses:
        sub_user = db.query(User).filter(User.id == a.sub_user_id).first()
        if sub_user:
            result.append(AccessResponse(
                id=a.id,
                sub_user_id=a.sub_user_id,
                sub_username=sub_user.username,
                sub_display_name=sub_user.display_name,
                role=AccountRoleResponse.model_validate(a.role),
                granted_at=a.granted_at,
            ))
    return result


@router.post("/access", status_code=201)
async def grant_access(
    request: AccessGrantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant a role to a user by username."""
    sub_user = db.query(User).filter(User.username == request.username).first()
    if not sub_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if sub_user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot grant access to yourself")

    role = _get_role_or_404(request.role_id, current_user.id, db)

    existing = db.query(AccountAccess).filter(
        AccountAccess.owner_user_id == current_user.id,
        AccountAccess.sub_user_id == sub_user.id,
    ).first()
    if existing:
        # Update the role on the existing grant
        existing.role_id = role.id
        existing.granted_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        access = existing
    else:
        access = AccountAccess(
            owner_user_id=current_user.id,
            sub_user_id=sub_user.id,
            role_id=role.id,
            granted_at=datetime.utcnow(),
        )
        db.add(access)
        db.commit()
        db.refresh(access)

    return AccessResponse(
        id=access.id,
        sub_user_id=sub_user.id,
        sub_username=sub_user.username,
        sub_display_name=sub_user.display_name,
        role=AccountRoleResponse.model_validate(access.role),
        granted_at=access.granted_at,
    )


@router.delete("/access/{sub_user_id}", status_code=204)
async def revoke_access(
    sub_user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a user's access to the current user's account."""
    access = db.query(AccountAccess).filter(
        AccountAccess.owner_user_id == current_user.id,
        AccountAccess.sub_user_id == sub_user_id,
    ).first()
    if not access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access grant not found")
    db.delete(access)
    db.commit()


# ── Sub-user perspective ───────────────────────────────────────────────────────

@router.get("/my-access", response_model=List[MyAccessResponse])
async def list_my_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all accounts the current user has been granted access to."""
    accesses = (
        db.query(AccountAccess)
        .filter(AccountAccess.sub_user_id == current_user.id)
        .all()
    )
    result = []
    for a in accesses:
        owner = db.query(User).filter(User.id == a.owner_user_id).first()
        if owner:
            result.append(MyAccessResponse(
                owner_user_id=a.owner_user_id,
                owner_username=owner.username,
                owner_display_name=owner.display_name,
                role=AccountRoleResponse.model_validate(a.role),
                granted_at=a.granted_at,
            ))
    return result
