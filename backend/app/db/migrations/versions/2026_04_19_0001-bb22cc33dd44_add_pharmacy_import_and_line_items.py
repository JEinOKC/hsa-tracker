"""add_pharmacy_import_and_line_items

Revision ID: bb22cc33dd44
Revises: aa11bb22cc33
Create Date: 2026-04-19 00:01:00.000000

Adds three tables for the retailer purchase import feature:
  - pharmacy_import_batches: audit record per CSV upload
  - pharmacy_fills: one row per prescription fill from a pharmacy CSV
  - receipt_line_items: itemized line items for non-pharmacy receipts
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "bb22cc33dd44"
down_revision = "aa11bb22cc33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pharmacy_import_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("matched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unmatched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_pharmacy_import_batches_user_id", "pharmacy_import_batches", ["user_id"])

    op.create_table(
        "pharmacy_fills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_batch_id", UUID(as_uuid=True), sa.ForeignKey("pharmacy_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", UUID(as_uuid=True), sa.ForeignKey("bank_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("member_name", sa.String(200), nullable=True),
        sa.Column("drug_name", sa.String(500), nullable=False),
        sa.Column("rx_number", sa.String(100), nullable=True),
        sa.Column("fill_date", sa.Date, nullable=False),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("pharmacy", sa.String(200), nullable=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_pharmacy_fills_user_id", "pharmacy_fills", ["user_id"])
    op.create_index("ix_pharmacy_fills_fill_date", "pharmacy_fills", ["fill_date"])
    op.create_index("ix_pharmacy_fills_transaction_id", "pharmacy_fills", ["transaction_id"])
    op.create_index("ix_pharmacy_fills_import_batch_id", "pharmacy_fills", ["import_batch_id"])

    op.create_table(
        "receipt_line_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("transaction_id", UUID(as_uuid=True), sa.ForeignKey("bank_transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_hsa_eligible", sa.Boolean, nullable=True),
        sa.Column("hsa_category", sa.String(100), nullable=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.CheckConstraint("source IN ('csv_generic', 'manual')", name="ck_receipt_line_item_source"),
    )
    op.create_index("ix_receipt_line_items_transaction_id", "receipt_line_items", ["transaction_id"])
    op.create_index("ix_receipt_line_items_user_id", "receipt_line_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_receipt_line_items_user_id", table_name="receipt_line_items")
    op.drop_index("ix_receipt_line_items_transaction_id", table_name="receipt_line_items")
    op.drop_table("receipt_line_items")

    op.drop_index("ix_pharmacy_fills_import_batch_id", table_name="pharmacy_fills")
    op.drop_index("ix_pharmacy_fills_transaction_id", table_name="pharmacy_fills")
    op.drop_index("ix_pharmacy_fills_fill_date", table_name="pharmacy_fills")
    op.drop_index("ix_pharmacy_fills_user_id", table_name="pharmacy_fills")
    op.drop_table("pharmacy_fills")

    op.drop_index("ix_pharmacy_import_batches_user_id", table_name="pharmacy_import_batches")
    op.drop_table("pharmacy_import_batches")
