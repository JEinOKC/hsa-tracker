"""Letter of Medical Necessity (LMN) document endpoints.

Endpoints:
  POST   /families/{member_id}/lmn/presign              - request a presigned S3 PUT URL
  POST   /families/{member_id}/lmn/{lmn_id}/confirm     - confirm upload completed
  GET    /families/{member_id}/lmn                       - list confirmed LMNs for a member
  GET    /families/lmn                                   - list all confirmed LMNs in household
  PATCH  /families/{member_id}/lmn/{lmn_id}              - update LMN metadata
  DELETE /families/{member_id}/lmn/{lmn_id}              - delete an LMN document
"""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.bank import BankTransaction
from app.models.family import FamilyMember
from app.models.household import HouseholdMembership
from app.models.lmn import LmnDocument
from app.models.user import User
from app.services.s3 import build_lmn_s3_key, s3_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LmnPresignRequest(BaseModel):
    filename: str
    content_type: str
    file_size_bytes: int
    label: Optional[str] = None
    provider_name: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    notes: Optional[str] = None


class LmnPresignResponse(BaseModel):
    lmn_id: UUID
    upload_url: str
    s3_key: str


class LmnDocumentResponse(BaseModel):
    id: UUID
    family_member_id: UUID
    family_member_name: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    label: Optional[str]
    provider_name: Optional[str]
    issue_date: Optional[date]
    expiration_date: Optional[date]
    notes: Optional[str]
    uploaded_at: datetime
    url: str

    class Config:
        from_attributes = True


class LmnDocumentUpdate(BaseModel):
    label: Optional[str] = None
    provider_name: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_member_or_404(member_id: UUID, user: User, db: Session, operation: str = "read") -> FamilyMember:
    """Return the member if user is in the same household, else 404/403."""
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found.")
    membership = db.query(HouseholdMembership).filter(
        HouseholdMembership.user_id == user.id,
        HouseholdMembership.household_id == member.household_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Family member not found.")
    if operation in ("write", "delete"):
        role = membership.role
        can = role.can_write_documents if operation == "write" else role.can_delete_documents
        if not can and not membership.is_admin:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    return member


def _get_lmn_or_404(lmn_id: UUID, member_id: UUID, db: Session) -> LmnDocument:
    doc = (
        db.query(LmnDocument)
        .filter(LmnDocument.id == lmn_id, LmnDocument.family_member_id == member_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="LMN document not found.")
    return doc


def _lmn_to_response(doc: LmnDocument, member_name: str) -> LmnDocumentResponse:
    return LmnDocumentResponse(
        id=doc.id,
        family_member_id=doc.family_member_id,
        family_member_name=member_name,
        original_filename=doc.original_filename,
        content_type=doc.content_type,
        file_size_bytes=doc.file_size_bytes,
        label=doc.label,
        provider_name=doc.provider_name,
        issue_date=doc.issue_date,
        expiration_date=doc.expiration_date,
        notes=doc.notes,
        uploaded_at=doc.uploaded_at,
        url=s3_service.generate_presigned_get_url(doc.s3_key),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/lmn",
    response_model=List[LmnDocumentResponse],
)
async def list_all_lmn_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all confirmed LMN documents across all family members in the household."""
    membership = db.query(HouseholdMembership).filter(
        HouseholdMembership.user_id == current_user.id,
    ).first()
    if not membership:
        return []

    docs = (
        db.query(LmnDocument)
        .join(FamilyMember, FamilyMember.id == LmnDocument.family_member_id)
        .filter(
            FamilyMember.household_id == membership.household_id,
            LmnDocument.status == "confirmed",
        )
        .order_by(LmnDocument.uploaded_at.desc())
        .all()
    )
    return [_lmn_to_response(d, d.family_member.name) for d in docs]


@router.post(
    "/{member_id}/lmn/presign",
    response_model=LmnPresignResponse,
    status_code=201,
)
async def presign_lmn_upload(
    member_id: UUID,
    payload: LmnPresignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a presigned S3 PUT URL for uploading an LMN document."""
    _get_member_or_404(member_id, current_user, db, operation="write")

    allowed_types = [t.strip() for t in settings.allowed_mime_types.split(",")]
    if payload.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {payload.content_type}. Allowed: {', '.join(allowed_types)}",
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if payload.file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb} MB.",
        )

    s3_key = build_lmn_s3_key(
        settings.app_env,
        str(current_user.id),
        str(member_id),
        payload.filename,
    )
    upload_url = s3_service.generate_presigned_put_url(s3_key, payload.content_type)

    doc = LmnDocument(
        family_member_id=member_id,
        user_id=current_user.id,
        s3_key=s3_key,
        original_filename=payload.filename,
        content_type=payload.content_type,
        file_size_bytes=payload.file_size_bytes,
        status="pending",
        label=payload.label,
        provider_name=payload.provider_name,
        issue_date=payload.issue_date,
        expiration_date=payload.expiration_date,
        notes=payload.notes,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return LmnPresignResponse(lmn_id=doc.id, upload_url=upload_url, s3_key=s3_key)


@router.post(
    "/{member_id}/lmn/{lmn_id}/confirm",
    response_model=LmnDocumentResponse,
)
async def confirm_lmn_upload(
    member_id: UUID,
    lmn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm that the client's S3 PUT completed successfully."""
    member = _get_member_or_404(member_id, current_user, db)
    doc = _get_lmn_or_404(lmn_id, member_id, db)

    if doc.status != "pending":
        raise HTTPException(status_code=409, detail="Document is already confirmed.")

    if not s3_service.object_exists(doc.s3_key):
        raise HTTPException(
            status_code=422,
            detail="Upload not found in S3. Complete the file upload before confirming.",
        )

    doc.status = "confirmed"
    db.commit()
    db.refresh(doc)

    return _lmn_to_response(doc, member.name)


@router.get(
    "/{member_id}/lmn",
    response_model=List[LmnDocumentResponse],
)
async def list_member_lmn_documents(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all confirmed LMN documents for a family member."""
    member = _get_member_or_404(member_id, current_user, db)

    docs = (
        db.query(LmnDocument)
        .filter(
            LmnDocument.family_member_id == member_id,
            LmnDocument.status == "confirmed",
        )
        .order_by(LmnDocument.uploaded_at.desc())
        .all()
    )
    return [_lmn_to_response(d, member.name) for d in docs]


@router.patch(
    "/{member_id}/lmn/{lmn_id}",
    response_model=LmnDocumentResponse,
)
async def update_lmn_document(
    member_id: UUID,
    lmn_id: UUID,
    payload: LmnDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update metadata on an LMN document."""
    member = _get_member_or_404(member_id, current_user, db, operation="write")
    doc = _get_lmn_or_404(lmn_id, member_id, db)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)

    db.commit()
    db.refresh(doc)

    return _lmn_to_response(doc, member.name)


@router.delete(
    "/{member_id}/lmn/{lmn_id}",
    status_code=204,
)
async def delete_lmn_document(
    member_id: UUID,
    lmn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an LMN document from S3 and the database.

    Also clears lmn_document_id on any transactions that reference this LMN.
    """
    _get_member_or_404(member_id, current_user, db, operation="delete")
    doc = _get_lmn_or_404(lmn_id, member_id, db)

    # Clear references on transactions
    db.query(BankTransaction).filter(
        BankTransaction.lmn_document_id == doc.id,
    ).update({"lmn_document_id": None})

    s3_service.delete(doc.s3_key)
    db.delete(doc)
    db.commit()
