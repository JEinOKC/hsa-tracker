"""Letter of Medical Necessity (LMN) document model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class LmnDocument(Base):
    """A Letter of Medical Necessity uploaded for a family member.

    LMNs are uploaded once per family member and can be referenced by
    multiple transactions that require proof of medical necessity.
    """

    __tablename__ = "lmn_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    s3_key = Column(String(1024), nullable=False)
    original_filename = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # "pending" | "confirmed"

    # Metadata
    label = Column(String(255), nullable=True)          # e.g. "Orthodontic LMN 2026"
    provider_name = Column(String(255), nullable=True)  # doctor/provider who wrote the LMN
    issue_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    family_member = relationship("FamilyMember", back_populates="lmn_documents")

    def __repr__(self):
        return f"<LmnDocument({self.original_filename} for member {self.family_member_id})>"
