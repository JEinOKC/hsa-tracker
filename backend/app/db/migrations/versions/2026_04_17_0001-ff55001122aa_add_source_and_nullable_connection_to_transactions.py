"""add_source_and_nullable_connection_to_transactions

Revision ID: ff55001122aa
Revises: ee44ff550011
Create Date: 2026-04-17 00:01:00.000000

Adds a 'source' column to bank_transactions to distinguish manually-entered
transactions from Teller-synced ones, and makes connection_id nullable so
manual transactions can exist without a bank connection.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "ff55001122aa"
down_revision: Union[str, None] = "ee44ff550011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id for direct ownership (needed by manual transactions without a connection)
    op.add_column(
        "bank_transactions",
        sa.Column("user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_bank_transactions_user_id",
        "bank_transactions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_bank_transactions_user_id", "bank_transactions", ["user_id"])

    # Add source column (default 'teller' for all existing rows)
    op.add_column(
        "bank_transactions",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="teller",
        ),
    )
    op.create_check_constraint(
        "ck_bank_txn_source",
        "bank_transactions",
        "source IN ('teller', 'manual')",
    )
    # Make connection_id nullable so manual transactions need no bank connection
    op.alter_column(
        "bank_transactions",
        "connection_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    # provider and provider_transaction_id are also nullable for manual rows
    op.alter_column(
        "bank_transactions",
        "provider",
        existing_type=sa.String(50),
        nullable=True,
    )
    op.alter_column(
        "bank_transactions",
        "provider_transaction_id",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    op.drop_index("ix_bank_transactions_user_id", "bank_transactions")
    op.drop_constraint("fk_bank_transactions_user_id", "bank_transactions", type_="foreignkey")
    op.drop_column("bank_transactions", "user_id")

    op.alter_column(
        "bank_transactions",
        "provider_transaction_id",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.alter_column(
        "bank_transactions",
        "provider",
        existing_type=sa.String(50),
        nullable=False,
    )
    op.alter_column(
        "bank_transactions",
        "connection_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_constraint("ck_bank_txn_source", "bank_transactions", type_="check")
    op.drop_column("bank_transactions", "source")
