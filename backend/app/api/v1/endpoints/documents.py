"""Receipt / document endpoints for bank transactions.

Endpoints:
  POST   /bank/transactions/{id}/documents/presign           - request a presigned S3 PUT URL
  POST   /bank/transactions/{id}/documents/{doc_id}/confirm  - confirm upload completed
  GET    /bank/transactions/{id}/documents                   - list confirmed documents
  DELETE /bank/transactions/{id}/documents/{doc_id}          - delete a document
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.bank import BankConnection, BankTransaction, TransactionDocument
from app.models.user import User
from app.services.s3 import build_s3_key, s3_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PresignRequest(BaseModel):
    filename: str
    content_type: str
    file_size_bytes: int


class PresignResponse(BaseModel):
    document_id: UUID
    upload_url: str
    s3_key: str


class DocumentResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    original_filename: str
    content_type: str
    file_size_bytes: int
    uploaded_at: datetime
    url: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_transaction_or_404(transaction_id: UUID, user: User, db: Session) -> BankTransaction:
    """Return the transaction if it belongs to the current user, else 404."""
    user_connection_ids = (
        db.query(BankConnection.id)
        .filter(BankConnection.user_id == user.id)
        .subquery()
    )
    txn = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.id == transaction_id,
            BankTransaction.connection_id.in_(user_connection_ids),
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return txn


def _get_document_or_404(doc_id: UUID, transaction_id: UUID, user: User, db: Session) -> TransactionDocument:
    doc = (
        db.query(TransactionDocument)
        .filter(
            TransactionDocument.id == doc_id,
            TransactionDocument.transaction_id == transaction_id,
            TransactionDocument.user_id == user.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


def _doc_to_response(doc: TransactionDocument) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        transaction_id=doc.transaction_id,
        original_filename=doc.original_filename,
        content_type=doc.content_type,
        file_size_bytes=doc.file_size_bytes,
        uploaded_at=doc.uploaded_at,
        url=s3_service.generate_presigned_get_url(doc.s3_key),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/transactions/{transaction_id}/documents/presign",
    response_model=PresignResponse,
    status_code=201,
)
async def presign_document_upload(
    transaction_id: UUID,
    payload: PresignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a presigned S3 PUT URL so the client can upload directly.

    Creates a pending TransactionDocument row. The client must call /confirm
    after the S3 PUT succeeds.
    """
    _get_transaction_or_404(transaction_id, current_user, db)

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

    s3_key = build_s3_key(
        settings.app_env,
        str(current_user.id),
        str(transaction_id),
        payload.filename,
    )
    upload_url = s3_service.generate_presigned_put_url(s3_key, payload.content_type)

    doc = TransactionDocument(
        transaction_id=transaction_id,
        user_id=current_user.id,
        s3_key=s3_key,
        original_filename=payload.filename,
        content_type=payload.content_type,
        file_size_bytes=payload.file_size_bytes,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return PresignResponse(document_id=doc.id, upload_url=upload_url, s3_key=s3_key)


@router.post(
    "/transactions/{transaction_id}/documents/{document_id}/confirm",
    response_model=DocumentResponse,
)
async def confirm_document_upload(
    transaction_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm that the client's S3 PUT completed successfully.

    Verifies the object exists in S3, then marks the document as confirmed.
    Only confirmed documents appear in the document list.
    """
    _get_transaction_or_404(transaction_id, current_user, db)
    doc = _get_document_or_404(document_id, transaction_id, current_user, db)

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

    return _doc_to_response(doc)


@router.get(
    "/transactions/{transaction_id}/documents",
    response_model=list[DocumentResponse],
)
async def list_documents(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all confirmed documents for a transaction, each with a fresh presigned GET URL."""
    _get_transaction_or_404(transaction_id, current_user, db)

    docs = (
        db.query(TransactionDocument)
        .filter(
            TransactionDocument.transaction_id == transaction_id,
            TransactionDocument.user_id == current_user.id,
            TransactionDocument.status == "confirmed",
        )
        .order_by(TransactionDocument.uploaded_at.asc())
        .all()
    )
    return [_doc_to_response(d) for d in docs]


@router.delete(
    "/transactions/{transaction_id}/documents/{document_id}",
    status_code=204,
)
async def delete_document(
    transaction_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document from S3 and remove its database record."""
    _get_transaction_or_404(transaction_id, current_user, db)
    doc = _get_document_or_404(document_id, transaction_id, current_user, db)

    s3_service.delete(doc.s3_key)
    db.delete(doc)
    db.commit()
