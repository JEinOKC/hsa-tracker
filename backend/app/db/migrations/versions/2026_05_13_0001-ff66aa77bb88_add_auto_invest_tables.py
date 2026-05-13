"""add_auto_invest_tables

Revision ID: ff66aa77bb88
Revises: ee55ff6611aa
Create Date: 2026-05-13 00:01:00.000000

Adds two tables for recurring paycheck auto-invest schedules:
  - auto_invest_schedules: per-account schedule (amount, frequency, next date)
  - auto_invest_allocations: per-holding percentage splits within a schedule
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "ff66aa77bb88"
down_revision = "ee55ff6611aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auto_invest_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("hsa_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contribution_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="biweekly"),
        sa.Column("next_contribution_date", sa.Date, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "frequency IN ('biweekly', 'weekly', 'monthly')",
            name="ck_auto_invest_frequency",
        ),
    )
    op.create_index("ix_auto_invest_schedules_account_id", "auto_invest_schedules", ["account_id"])
    op.create_index("ix_auto_invest_schedules_user_id", "auto_invest_schedules", ["user_id"])

    op.create_table(
        "auto_invest_allocations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("schedule_id", UUID(as_uuid=True), sa.ForeignKey("auto_invest_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("holding_id", UUID(as_uuid=True), sa.ForeignKey("hsa_holdings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.CheckConstraint("percentage > 0 AND percentage <= 100", name="ck_auto_invest_alloc_pct"),
    )
    op.create_index("ix_auto_invest_allocations_schedule_id", "auto_invest_allocations", ["schedule_id"])
    op.create_index("ix_auto_invest_allocations_holding_id", "auto_invest_allocations", ["holding_id"])


def downgrade() -> None:
    op.drop_index("ix_auto_invest_allocations_holding_id", table_name="auto_invest_allocations")
    op.drop_index("ix_auto_invest_allocations_schedule_id", table_name="auto_invest_allocations")
    op.drop_table("auto_invest_allocations")
    op.drop_index("ix_auto_invest_schedules_user_id", table_name="auto_invest_schedules")
    op.drop_index("ix_auto_invest_schedules_account_id", table_name="auto_invest_schedules")
    op.drop_table("auto_invest_schedules")
