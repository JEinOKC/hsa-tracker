"""Family member management endpoints.

Endpoints:
  GET    /families/                                       - list family members for current user
  POST   /families/                                       - create a family member
  GET    /families/{member_id}                            - get a family member
  PUT    /families/{member_id}                            - update a family member
  DELETE /families/{member_id}                            - deactivate a family member

  GET    /families/{member_id}/eligibility                - list eligibility periods
  POST   /families/{member_id}/eligibility                - add an eligibility period
  PUT    /families/{member_id}/eligibility/{period_id}    - update an eligibility period
  DELETE /families/{member_id}/eligibility/{period_id}    - delete an eligibility period

  GET    /families/eligibility/check                      - check if a member was eligible on a given date
"""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.family import FamilyMember, HsaEligibilityPeriod
from app.models.user import User

router = APIRouter()

VALID_RELATIONSHIPS = {"self", "spouse", "child", "other"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EligibilityPeriodCreate(BaseModel):
    start_date: date
    end_date: Optional[date] = None
    notes: Optional[str] = None


class EligibilityPeriodUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class EligibilityPeriodResponse(BaseModel):
    id: UUID
    family_member_id: UUID
    start_date: date
    end_date: Optional[date]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class FamilyMemberCreate(BaseModel):
    name: str
    member_relationship: str
    date_of_birth: Optional[date] = None
    is_tax_dependent: bool = False
    # Optionally seed the first eligibility period at creation time
    eligibility_start: Optional[date] = None
    eligibility_end: Optional[date] = None


class FamilyMemberUpdate(BaseModel):
    name: Optional[str] = None
    member_relationship: Optional[str] = None
    date_of_birth: Optional[date] = None
    is_tax_dependent: Optional[bool] = None
    is_active: Optional[bool] = None


class FamilyMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    member_relationship: str
    date_of_birth: Optional[date]
    is_tax_dependent: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    eligibility_periods: List[EligibilityPeriodResponse] = []

    class Config:
        from_attributes = True


class EligibilityCheckResponse(BaseModel):
    member_id: UUID
    expense_date: date
    is_eligible: bool
    matched_period: Optional[EligibilityPeriodResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_member_or_404(member_id: UUID, user_id: UUID, db: Session) -> FamilyMember:
    member = (
        db.query(FamilyMember)
        .filter(FamilyMember.id == member_id, FamilyMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found.")
    return member


def _get_period_or_404(period_id: UUID, member_id: UUID, db: Session) -> HsaEligibilityPeriod:
    period = (
        db.query(HsaEligibilityPeriod)
        .filter(
            HsaEligibilityPeriod.id == period_id,
            HsaEligibilityPeriod.family_member_id == member_id,
        )
        .first()
    )
    if not period:
        raise HTTPException(status_code=404, detail="Eligibility period not found.")
    return period


def _check_eligible_on(member: FamilyMember, expense_date: date) -> Optional[HsaEligibilityPeriod]:
    """Return the first eligibility period that covers expense_date, or None."""
    for period in member.eligibility_periods:
        if period.start_date <= expense_date:
            if period.end_date is None or period.end_date >= expense_date:
                return period
    return None


# ---------------------------------------------------------------------------
# Family member endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[FamilyMemberResponse])
async def list_family_members(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all family members belonging to the current user."""
    query = db.query(FamilyMember).filter(FamilyMember.user_id == current_user.id)
    if not include_inactive:
        query = query.filter(FamilyMember.is_active == True)
    return query.order_by(FamilyMember.created_at).all()


@router.post("/", response_model=FamilyMemberResponse, status_code=201)
async def create_family_member(
    payload: FamilyMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a family member, optionally seeding their first eligibility period."""
    if payload.member_relationship not in VALID_RELATIONSHIPS:
        raise HTTPException(
            status_code=422,
            detail=f"member_relationship must be one of: {', '.join(sorted(VALID_RELATIONSHIPS))}",
        )

    member = FamilyMember(
        user_id=current_user.id,
        name=payload.name,
        member_relationship=payload.member_relationship,
        date_of_birth=payload.date_of_birth,
        is_tax_dependent=payload.is_tax_dependent,
    )
    db.add(member)
    db.flush()  # get member.id before adding the period

    if payload.eligibility_start:
        period = HsaEligibilityPeriod(
            family_member_id=member.id,
            start_date=payload.eligibility_start,
            end_date=payload.eligibility_end,
        )
        db.add(period)

    db.commit()
    db.refresh(member)
    return member


@router.get("/{member_id}", response_model=FamilyMemberResponse)
async def get_family_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_member_or_404(member_id, current_user.id, db)


@router.put("/{member_id}", response_model=FamilyMemberResponse)
async def update_family_member(
    member_id: UUID,
    payload: FamilyMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = _get_member_or_404(member_id, current_user.id, db)

    if payload.member_relationship is not None and payload.member_relationship not in VALID_RELATIONSHIPS:
        raise HTTPException(
            status_code=422,
            detail=f"member_relationship must be one of: {', '.join(sorted(VALID_RELATIONSHIPS))}",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)

    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=204)
async def deactivate_family_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete: marks the member inactive rather than deleting records."""
    member = _get_member_or_404(member_id, current_user.id, db)
    member.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Eligibility period sub-endpoints
# ---------------------------------------------------------------------------

@router.get("/{member_id}/eligibility", response_model=List[EligibilityPeriodResponse])
async def list_eligibility_periods(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = _get_member_or_404(member_id, current_user.id, db)
    return member.eligibility_periods


@router.post("/{member_id}/eligibility", response_model=EligibilityPeriodResponse, status_code=201)
async def add_eligibility_period(
    member_id: UUID,
    payload: EligibilityPeriodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = _get_member_or_404(member_id, current_user.id, db)

    if payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")

    period = HsaEligibilityPeriod(
        family_member_id=member.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        notes=payload.notes,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


@router.put("/{member_id}/eligibility/{period_id}", response_model=EligibilityPeriodResponse)
async def update_eligibility_period(
    member_id: UUID,
    period_id: UUID,
    payload: EligibilityPeriodUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_member_or_404(member_id, current_user.id, db)
    period = _get_period_or_404(period_id, member_id, db)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(period, field, value)

    if period.end_date and period.end_date < period.start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")

    db.commit()
    db.refresh(period)
    return period


@router.delete("/{member_id}/eligibility/{period_id}", status_code=204)
async def delete_eligibility_period(
    member_id: UUID,
    period_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_member_or_404(member_id, current_user.id, db)
    period = _get_period_or_404(period_id, member_id, db)
    db.delete(period)
    db.commit()


# ---------------------------------------------------------------------------
# Eligibility check
# ---------------------------------------------------------------------------

@router.get("/{member_id}/eligibility/check", response_model=EligibilityCheckResponse)
async def check_eligibility(
    member_id: UUID,
    expense_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return whether a family member was HSA-eligible on a given expense date."""
    member = _get_member_or_404(member_id, current_user.id, db)
    matched = _check_eligible_on(member, expense_date)
    return EligibilityCheckResponse(
        member_id=member_id,
        expense_date=expense_date,
        is_eligible=matched is not None,
        matched_period=EligibilityPeriodResponse.model_validate(matched) if matched else None,
    )
