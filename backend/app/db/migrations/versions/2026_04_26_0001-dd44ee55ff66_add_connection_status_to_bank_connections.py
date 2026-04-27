"""add_connection_status_to_bank_connections

Revision ID: dd44ee55ff66
Revises: cc33dd44ee55
Create Date: 2026-04-26 00:01:00.000000

Adds connection_status and connection_error columns to bank_connections
to track whether a Teller enrollment is still active.
"""

from alembic import op
import sqlalchemy as sa

revision = "dd44ee55ff66"
down_revision = "cc33dd44ee55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bank_connections",
        sa.Column("connection_status", sa.String(20), nullable=False, server_default="connected"),
    )
    op.add_column(
        "bank_connections",
        sa.Column("connection_error", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_bank_connection_status",
        "bank_connections",
        "connection_status IN ('connected', 'disconnected', 'error')",
    )
    op.create_index(
        "ix_bank_connections_connection_status",
        "bank_connections",
        ["connection_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_connections_connection_status", table_name="bank_connections")
    op.drop_constraint("ck_bank_connection_status", "bank_connections", type_="check")
    op.drop_column("bank_connections", "connection_error")
    op.drop_column("bank_connections", "connection_status")