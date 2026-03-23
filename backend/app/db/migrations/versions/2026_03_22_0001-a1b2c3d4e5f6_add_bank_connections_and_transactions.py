"""Add bank_connections and bank_transactions tables

Revision ID: a1b2c3d4e5f6
Revises: d95d1e3d9402
Create Date: 2026-03-22 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd95d1e3d9402'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bank_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('provider_account_id', sa.String(255), nullable=False),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column('account_type', sa.String(50), nullable=True),
        sa.Column('account_subtype', sa.String(50), nullable=True),
        sa.Column('institution_name', sa.String(255), nullable=True),
        sa.Column('last_four', sa.String(4), nullable=True),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_account_id', name='uq_bank_connection_provider_account'),
    )
    op.create_index('ix_bank_connections_provider_account_id', 'bank_connections', ['provider_account_id'])

    op.create_table(
        'bank_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('provider_transaction_id', sa.String(255), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('transaction_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['connection_id'], ['bank_connections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('connection_id', 'provider_transaction_id', name='uq_bank_txn_connection_provider_id'),
    )
    op.create_index('ix_bank_transactions_connection_id', 'bank_transactions', ['connection_id'])
    op.create_index('ix_bank_transactions_provider_transaction_id', 'bank_transactions', ['provider_transaction_id'])
    op.create_index('ix_bank_transactions_transaction_date', 'bank_transactions', ['transaction_date'])


def downgrade() -> None:
    op.drop_table('bank_transactions')
    op.drop_table('bank_connections')
