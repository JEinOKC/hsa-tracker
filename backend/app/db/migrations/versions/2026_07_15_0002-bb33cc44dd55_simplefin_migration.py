"""simplefin_migration

Revision ID: bb33cc44dd55
Revises: aa22bb33cc44
Create Date: 2026-07-15 00:02:00.000000

Replace Sophtron with SimpleFIN Bridge:

1. Update ck_bank_txn_source: replace 'sophtron' with 'simplefin'.
   Any existing rows with source='sophtron' are updated to 'simplefin'.

2. Mark all Sophtron bank_connections as disconnected so users are
   prompted to reconnect via SimpleFIN.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'bb33cc44dd55'
down_revision: Union[str, None] = 'aa22bb33cc44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Migrate existing sophtron transaction rows
    op.execute("UPDATE bank_transactions SET source = 'simplefin' WHERE source = 'sophtron'")

    # 2. Swap the source CHECK constraint
    op.drop_constraint('ck_bank_txn_source', 'bank_transactions', type_='check')
    op.create_check_constraint(
        'ck_bank_txn_source',
        'bank_transactions',
        "source IN ('teller', 'simplefin', 'manual')",
    )

    # 3. Mark Sophtron connections as disconnected; users will reconnect via SimpleFIN
    op.execute(
        """
        UPDATE bank_connections
        SET
            connection_status = 'disconnected',
            connection_error  = 'Provider migration: please reconnect via SimpleFIN',
            enrollment_token  = NULL
        WHERE provider = 'sophtron'
          AND connection_status != 'disconnected'
        """
    )


def downgrade() -> None:
    # Revert transaction source
    op.execute("UPDATE bank_transactions SET source = 'sophtron' WHERE source = 'simplefin'")

    op.drop_constraint('ck_bank_txn_source', 'bank_transactions', type_='check')
    op.create_check_constraint(
        'ck_bank_txn_source',
        'bank_transactions',
        "source IN ('teller', 'sophtron', 'manual')",
    )
