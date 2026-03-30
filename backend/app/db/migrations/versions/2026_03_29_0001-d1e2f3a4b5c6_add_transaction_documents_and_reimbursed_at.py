"""Add transaction_documents table and reimbursed_at column to bank_transactions

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-03-29 00:01:00.000000

Adds:
  transaction_documents - stores S3 receipt/document metadata per transaction.
    Each row represents one file attached to a bank transaction. The s3_key
    encodes the env/user/txn path so the single S3 bucket stays organised
    across dev/staging/production. Status is "pending" until the client
    confirms the S3 PUT completed.

  bank_transactions.reimbursed_at - nullable timestamp recording when a
    transaction was reimbursed. Automatically set by the PATCH endpoint when
    reimbursement_status transitions to "reimbursed".
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'transaction_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('s3_key', sa.String(length=1024), nullable=False),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['transaction_id'], ['bank_transactions.id'],
            ondelete='CASCADE',
            name='fk_transaction_documents_transaction_id',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            ondelete='CASCADE',
            name='fk_transaction_documents_user_id',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_transaction_documents_transaction_id',
        'transaction_documents',
        ['transaction_id'],
    )
    op.create_index(
        'ix_transaction_documents_user_id',
        'transaction_documents',
        ['user_id'],
    )

    op.add_column(
        'bank_transactions',
        sa.Column('reimbursed_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('bank_transactions', 'reimbursed_at')

    op.drop_index('ix_transaction_documents_user_id', table_name='transaction_documents')
    op.drop_index('ix_transaction_documents_transaction_id', table_name='transaction_documents')
    op.drop_table('transaction_documents')
