"""Receipt management endpoints"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transaction import Transaction, Receipt
from app.models.family import FamilyMember
from app.models.user import User
from app.schemas.transaction import ReceiptCreate, ReceiptResponse
from app.utils.security import get_current_user
from app.services.s3_service import s3_service
from app.config import settings

router = APIRouter()


def get_user_family_id(db: Session, user: User) -> UUID:
    """Get the family_id for the current user"""
    family_member = db.query(FamilyMember).filter(
        FamilyMember.user_id == user.id
    ).first()

    if not family_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a family"
        )

    return family_member.family_id


@router.post("/upload-url", status_code=200)
async def get_upload_url(
    transaction_id: UUID,
    file_name: str,
    mime_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a pre-signed S3 URL for uploading a receipt

    This endpoint returns a pre-signed URL that the client can use
    to upload a file directly to S3, bypassing the backend.

    After uploading to S3, the client should call POST /receipts
    to create the receipt record in the database.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Verify transaction exists and belongs to user's family
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.family_id == family_id
    ).first()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    # Validate MIME type
    if mime_type not in settings.allowed_mime_types_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(settings.allowed_mime_types_list)}"
        )

    # Generate pre-signed upload URL
    try:
        upload_data = s3_service.generate_upload_url(
            file_name=file_name,
            mime_type=mime_type,
            family_id=family_id,
            transaction_id=transaction_id,
        )

        return {
            "upload_url": upload_data["upload_url"],
            "s3_key": upload_data["s3_key"],
            "fields": upload_data["fields"],
            "transaction_id": str(transaction_id),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate upload URL: {str(e)}"
        )


@router.post("/", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    transaction_id: UUID,
    receipt: ReceiptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a receipt record after uploading to S3

    This endpoint should be called after successfully uploading
    a file to S3 using the pre-signed URL from POST /receipts/upload-url.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Verify transaction exists and belongs to user's family
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.family_id == family_id
    ).first()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    # Verify file exists in S3
    if not s3_service.check_file_exists(receipt.s3_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File not found in S3. Please upload the file first."
        )

    # Create receipt record
    db_receipt = Receipt(
        transaction_id=transaction_id,
        file_name=receipt.file_name,
        file_size=receipt.file_size,
        mime_type=receipt.mime_type,
        s3_key=receipt.s3_key,
        s3_bucket=receipt.s3_bucket,
        thumbnail_s3_key=receipt.thumbnail_s3_key,
        uploaded_by_user_id=current_user.id,
    )

    db.add(db_receipt)
    db.commit()
    db.refresh(db_receipt)

    return db_receipt


@router.get("/transaction/{transaction_id}", response_model=List[ReceiptResponse])
async def list_receipts_for_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all receipts for a specific transaction
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Verify transaction exists and belongs to user's family
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.family_id == family_id
    ).first()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    # Get all receipts for this transaction
    receipts = db.query(Receipt).filter(
        Receipt.transaction_id == transaction_id
    ).order_by(Receipt.upload_date.desc()).all()

    return receipts


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific receipt by ID
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query receipt with transaction to verify family access
    receipt = db.query(Receipt).join(Transaction).filter(
        Receipt.id == receipt_id,
        Transaction.family_id == family_id
    ).first()

    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )

    return receipt


@router.get("/{receipt_id}/download", status_code=200)
async def get_receipt_download_url(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a pre-signed S3 URL for downloading a receipt

    Returns a temporary URL that the client can use to download
    the receipt file directly from S3.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query receipt with transaction to verify family access
    receipt = db.query(Receipt).join(Transaction).filter(
        Receipt.id == receipt_id,
        Transaction.family_id == family_id
    ).first()

    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )

    # Generate pre-signed download URL
    try:
        download_url = s3_service.generate_download_url(receipt.s3_key)

        return {
            "download_url": download_url,
            "file_name": receipt.file_name,
            "mime_type": receipt.mime_type,
            "expires_in": 3600,  # 1 hour
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        )


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a receipt

    Deletes both the database record and the file from S3.
    """
    # Get user's family
    family_id = get_user_family_id(db, current_user)

    # Query receipt with transaction to verify family access
    receipt = db.query(Receipt).join(Transaction).filter(
        Receipt.id == receipt_id,
        Transaction.family_id == family_id
    ).first()

    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )

    # Delete from S3
    s3_service.delete_file(receipt.s3_key)

    # Delete thumbnail if it exists
    if receipt.thumbnail_s3_key:
        s3_service.delete_file(receipt.thumbnail_s3_key)

    # Delete from database
    db.delete(receipt)
    db.commit()

    return None
