"""sophtron_migration

Revision ID: aa22bb33cc44
Revises: a1b2c3d4e5f6
Create Date: 2026-07-15 00:01:00.000000

Three schema changes for the Teller → Sophtron provider migration:

1. Expand ck_bank_txn_source to include 'sophtron' alongside 'teller' and 'manual'.
2. Rename ck_hsa_rule_condition_field to allow 'provider_category' in addition to
   (and instead of) 'teller_category'.  Existing rows with field='teller_category'
   are updated to 'provider_category' so rules continue to fire after migration.
3. Data migration: mark all existing Teller bank_connections as disconnected so
   users are prompted to reconnect through the Sophtron widget.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'aa22bb33cc44'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Expand source CHECK to include 'sophtron'
    op.drop_constraint('ck_bank_txn_source', 'bank_transactions', type_='check')
    op.create_check_constraint(
        'ck_bank_txn_source',
        'bank_transactions',
        "source IN ('teller', 'sophtron', 'manual')",
    )

    # 2. Rename teller_category → provider_category in rule conditions
    #    First update existing rows so data is consistent before the constraint changes.
    op.execute(
        "UPDATE hsa_rule_conditions SET field = 'provider_category' WHERE field = 'teller_category'"
    )
    op.drop_constraint('ck_hsa_rule_condition_field', 'hsa_rule_conditions', type_='check')
    op.create_check_constraint(
        'ck_hsa_rule_condition_field',
        'hsa_rule_conditions',
        "field IN ('counterparty_name', 'description', 'amount', 'date', 'provider_category')",
    )

    # 3. Mark existing Teller connections as disconnected with a migration message.
    #    Users will be prompted to reconnect via the Sophtron widget.
    op.execute(
        """
        UPDATE bank_connections
        SET
            connection_status = 'disconnected',
            connection_error  = 'Provider migration: please reconnect via Sophtron',
            enrollment_token  = NULL
        WHERE provider = 'teller'
          AND connection_status != 'disconnected'
        """
    )


def downgrade() -> None:
    # Revert rule condition field constraint
    op.execute(
        "UPDATE hsa_rule_conditions SET field = 'teller_category' WHERE field = 'provider_category'"
    )
    op.drop_constraint('ck_hsa_rule_condition_field', 'hsa_rule_conditions', type_='check')
    op.create_check_constraint(
        'ck_hsa_rule_condition_field',
        'hsa_rule_conditions',
        "field IN ('counterparty_name', 'description', 'amount', 'date', 'teller_category')",
    )

    # Revert source CHECK (remove 'sophtron')
    op.drop_constraint('ck_bank_txn_source', 'bank_transactions', type_='check')
    op.create_check_constraint(
        'ck_bank_txn_source',
        'bank_transactions',
        "source IN ('teller', 'manual')",
    )

    # Note: the data migration (disconnecting Teller connections) is not reversed
    # because Teller is no longer operational.
