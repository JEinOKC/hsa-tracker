"""add_user_category_overrides

Revision ID: aa11bb22cc33
Revises: ff55001122aa
Create Date: 2026-04-18 00:01:00.000000

Adds user_category_overrides table so users can pin categories to always
show or always hide in Smart filter mode, overriding the adaptive defaults.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "aa11bb22cc33"
down_revision = "ff55001122aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_category_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("pin_mode", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "category", name="uq_user_category_override_user_category"),
        sa.CheckConstraint("pin_mode IN ('show', 'hide')", name="ck_user_category_override_pin_mode"),
    )
    op.create_index("ix_user_category_overrides_user_id", "user_category_overrides", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_category_overrides_user_id", table_name="user_category_overrides")
    op.drop_table("user_category_overrides")