"""add_holding_snapshots

Revision ID: ee55ff6611aa
Revises: dd44ee55ff66
Create Date: 2026-04-29 00:01:00.000000

Adds holding_snapshots table to record point-in-time snapshots of each
holding's shares, price, and computed value. One snapshot per holding per day
is upserted whenever prices are refreshed or share counts are edited.
holding_id is nullable (SET NULL on delete) so history survives if a holding
is later removed.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "ee55ff6611aa"
down_revision = "dd44ee55ff66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "holding_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "holding_id",
            UUID(as_uuid=True),
            sa.ForeignKey("hsa_holdings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("hsa_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("shares", sa.Numeric(16, 6), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("value", sa.Numeric(14, 2), nullable=False),
        sa.Column("snapshotted_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_holding_snapshots_holding_id", "holding_snapshots", ["holding_id"])
    op.create_index("ix_holding_snapshots_account_id", "holding_snapshots", ["account_id"])
    op.create_index("ix_holding_snapshots_user_id", "holding_snapshots", ["user_id"])
    op.create_index("ix_holding_snapshots_snapshotted_at", "holding_snapshots", ["snapshotted_at"])


def downgrade() -> None:
    op.drop_index("ix_holding_snapshots_snapshotted_at", table_name="holding_snapshots")
    op.drop_index("ix_holding_snapshots_user_id", table_name="holding_snapshots")
    op.drop_index("ix_holding_snapshots_account_id", table_name="holding_snapshots")
    op.drop_index("ix_holding_snapshots_holding_id", table_name="holding_snapshots")
    op.drop_table("holding_snapshots")
