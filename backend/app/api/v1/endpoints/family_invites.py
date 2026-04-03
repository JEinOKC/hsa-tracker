"""Family invite link endpoints — in-app invite generation with TTL and family PIN"""

import base64
import io
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

import qrcode
from coolname import generate_slug
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.family import FamilyMember
from app.models.household import HouseholdMembership, HouseholdRole
from app.models.user import FamilyInvite, User

router = APIRouter()

INVITE_TTL_HOURS = 72


# ── schemas ───────────────────────────────────────────────────────────────────

class CreateInviteRequest(BaseModel):
    label: Optional[str] = None
    require_pin: bool = True
    household_role_id: Optional[UUID] = None
    family_member_id: Optional[UUID] = None   # link invitee to an existing FamilyMember record


class InviteResponse(BaseModel):
    token: str
    label: Optional[str]
    invite_url: str
    qr_code_data_url: str
    expires_at: datetime
    require_pin: bool
    is_used: bool


class ValidateInviteResponse(BaseModel):
    valid: bool
    require_pin: bool
    expires_at: Optional[datetime]
    family_member_name: Optional[str] = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_invite_url(token: str) -> str:
    return f"{settings.webauthn_origin}/invite/{token}"


def _make_qr_data_url(url: str) -> str:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _invite_to_response(invite: FamilyInvite) -> InviteResponse:
    url = _make_invite_url(invite.token)
    return InviteResponse(
        token=invite.token,
        label=invite.label,
        invite_url=url,
        qr_code_data_url=_make_qr_data_url(url),
        expires_at=invite.expires_at,
        require_pin=invite.require_pin,
        is_used=invite.is_used,
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=InviteResponse, status_code=201)
async def create_invite(
    request: CreateInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a new family invite link with QR code.
    The link expires in 72 hours and is single-use.
    """
    household_id = None
    if request.household_role_id:
        membership = db.query(HouseholdMembership).filter(
            HouseholdMembership.user_id == current_user.id
        ).first()
        if not membership:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are not in a household")
        if not membership.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only household admins can send household invites")
        role = db.query(HouseholdRole).filter(
            HouseholdRole.id == request.household_role_id,
            HouseholdRole.household_id == membership.household_id,
        ).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household role not found")
        household_id = membership.household_id

    token_str = generate_slug(3)
    expires_at = datetime.utcnow() + timedelta(hours=INVITE_TTL_HOURS)

    invite = FamilyInvite(
        token=token_str,
        label=request.label or None,
        created_by_user_id=current_user.id,
        expires_at=expires_at,
        require_pin=request.require_pin,
        household_id=household_id,
        household_role_id=request.household_role_id,
        family_member_id=request.family_member_id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return _invite_to_response(invite)


@router.get("", response_model=List[InviteResponse])
async def list_invites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all active (unused, unexpired) invites created by the current user."""
    now = datetime.utcnow()
    invites = (
        db.query(FamilyInvite)
        .filter(
            FamilyInvite.created_by_user_id == current_user.id,
            FamilyInvite.used_at.is_(None),
            FamilyInvite.expires_at > now,
        )
        .order_by(FamilyInvite.created_at.desc())
        .all()
    )
    return [_invite_to_response(i) for i in invites]


@router.delete("/{token}", status_code=204)
async def revoke_invite(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke (delete) an unused invite. Only the creator can revoke."""
    invite = db.query(FamilyInvite).filter(FamilyInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if str(invite.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your invite")
    if invite.is_used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite has already been used")
    db.delete(invite)
    db.commit()


@router.get("/validate/{token}", response_model=ValidateInviteResponse)
async def validate_invite(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Public endpoint — check if an invite token is valid.
    Used by the /invite/:token page to pre-fill the form and know if PIN is required.
    Intentionally returns minimal info (no creator details).
    """
    invite = db.query(FamilyInvite).filter(FamilyInvite.token == token).first()
    if not invite or not invite.is_valid:
        return ValidateInviteResponse(valid=False, require_pin=False, expires_at=None)
    family_member_name: Optional[str] = None
    if invite.family_member_id:
        fm = db.query(FamilyMember).filter(FamilyMember.id == invite.family_member_id).first()
        if fm:
            family_member_name = fm.name
    return ValidateInviteResponse(
        valid=True,
        require_pin=invite.require_pin,
        expires_at=invite.expires_at,
        family_member_name=family_member_name,
    )
