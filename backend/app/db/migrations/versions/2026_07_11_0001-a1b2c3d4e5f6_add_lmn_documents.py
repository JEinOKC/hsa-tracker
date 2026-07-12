"""add_lmn_documents

Revision ID: a1b2c3d4e5f6
Revises: ff66aa77bb88
Create Date: 2026-07-11 00:01:00.000000

Adds the lmn_documents table for Letters of Medical Necessity attached to
family members, and a foreign key on bank_transactions to associate a
transaction with an LMN.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic
revision = "a1b2c3d4e5f6"
down_revision = "ff66aa77bb88"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lmn_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "family_member_id",
            UUID(as_uuid=True),
            sa.ForeignKey("family_members.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("s3_key", sa.String(1024), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("provider_name", sa.String(255), nullable=True),
        sa.Column("issue_date", sa.Date, nullable=True),
        sa.Column("expiration_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "bank_transactions",
        sa.Column(
            "lmn_document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lmn_documents.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("bank_transactions", "lmn_document_id")
    op.drop_table("lmn_documents")
