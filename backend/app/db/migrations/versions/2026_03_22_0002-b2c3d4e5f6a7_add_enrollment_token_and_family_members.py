"""Add enrollment_token to bank_connections; add family_members and hsa_eligibility_periods

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-22 00:02:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add enrollment_token to existing bank_connections table
    op.add_column(
        'bank_connections',
        sa.Column('enrollment_token', sa.String(255), nullable=True),
    )

    # Family members
    op.create_table(
        'family_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('member_relationship', sa.String(50), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('is_tax_dependent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_family_members_user_id', 'family_members', ['user_id'])

    # HSA eligibility periods (one family member can have many non-overlapping periods)
    op.create_table(
        'hsa_eligibility_periods',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('family_member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['family_member_id'], ['family_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_hsa_eligibility_periods_family_member_id', 'hsa_eligibility_periods', ['family_member_id'])
    op.create_index('ix_hsa_eligibility_periods_start_date', 'hsa_eligibility_periods', ['start_date'])


def downgrade() -> None:
    op.drop_table('hsa_eligibility_periods')
    op.drop_table('family_members')
    op.drop_column('bank_connections', 'enrollment_token')
