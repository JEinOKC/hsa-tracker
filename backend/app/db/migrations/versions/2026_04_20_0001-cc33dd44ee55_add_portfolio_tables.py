"""add_portfolio_tables

Revision ID: cc33dd44ee55
Revises: bb22cc33dd44
Create Date: 2026-04-20 00:01:00.000000

Adds two tables for the HSA investment portfolio tracker:
  - hsa_accounts: manually-tracked HSA institution accounts (Fidelity, Rippling, etc.)
  - hsa_holdings: stock/fund positions within an account (ticker, shares, last known price)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "cc33dd44ee55"
down_revision = "bb22cc33dd44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hsa_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institution_name", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(255), nullable=True),
        sa.Column("account_type", sa.String(20), nullable=False, server_default="both"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("cash_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_balance_updated_at", sa.DateTime, nullable=True),
        sa.Column("last_checkin_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "account_type IN ('contribution', 'investment', 'both')",
            name="ck_hsa_account_type",
        ),
    )
    op.create_index("ix_hsa_accounts_user_id", "hsa_accounts", ["user_id"])

    op.create_table(
        "hsa_holdings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("hsa_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("shares", sa.Numeric(16, 6), nullable=False),
        sa.Column("last_known_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("last_price_fetched_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_hsa_holdings_account_id", "hsa_holdings", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_hsa_holdings_account_id", table_name="hsa_holdings")
    op.drop_table("hsa_holdings")
    op.drop_index("ix_hsa_accounts_user_id", table_name="hsa_accounts")
    op.drop_table("hsa_accounts")
