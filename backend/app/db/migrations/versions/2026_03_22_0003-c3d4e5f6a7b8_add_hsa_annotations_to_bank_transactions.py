"""Add user_id to bank_connections; add HSA annotation columns to bank_transactions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-22 00:03:00.000000

bank_connections was missing user_id, making all connections global across
users. This adds the FK and backfills NULL for existing rows (there should
be none in production yet).

HSA annotation columns on bank_transactions let users tag raw imported
transactions as HSA-eligible without a separate table:
  is_hsa_eligible   - NULL = unreviewed, TRUE = HSA, FALSE = not HSA
  family_member_id  - which family member this expense is for
  hsa_category      - e.g. "medical", "dental", "vision"
  reimbursement_status - "pending" | "reimbursed" | "not_needed"
  notes             - free-text user notes
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- bank_connections: add user_id ---
    op.add_column(
        'bank_connections',
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=True,   # nullable for backfill; tightened below
        ),
    )
    op.create_index('ix_bank_connections_user_id', 'bank_connections', ['user_id'])

    # --- bank_transactions: HSA annotation columns ---
    op.add_column(
        'bank_transactions',
        sa.Column('is_hsa_eligible', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'bank_transactions',
        sa.Column(
            'family_member_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('family_members.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.add_column(
        'bank_transactions',
        sa.Column('hsa_category', sa.String(100), nullable=True),
    )
    op.add_column(
        'bank_transactions',
        sa.Column('reimbursement_status', sa.String(20), nullable=True),
    )
    op.add_column(
        'bank_transactions',
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_index(
        'ix_bank_transactions_is_hsa_eligible',
        'bank_transactions',
        ['is_hsa_eligible'],
    )
    op.create_index(
        'ix_bank_transactions_family_member_id',
        'bank_transactions',
        ['family_member_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_bank_transactions_family_member_id', table_name='bank_transactions')
    op.drop_index('ix_bank_transactions_is_hsa_eligible', table_name='bank_transactions')
    op.drop_column('bank_transactions', 'notes')
    op.drop_column('bank_transactions', 'reimbursement_status')
    op.drop_column('bank_transactions', 'hsa_category')
    op.drop_column('bank_transactions', 'family_member_id')
    op.drop_column('bank_transactions', 'is_hsa_eligible')
    op.drop_index('ix_bank_connections_user_id', table_name='bank_connections')
    op.drop_column('bank_connections', 'user_id')
