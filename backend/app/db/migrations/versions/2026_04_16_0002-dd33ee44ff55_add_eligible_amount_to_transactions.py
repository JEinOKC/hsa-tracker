"""add_eligible_amount_to_transactions

Revision ID: dd33ee44ff55
Revises: cc11dd22ee33
Create Date: 2026-04-16 00:02:00.000000

Adds eligible_amount to bank_transactions so users can record that only a portion
of a charge is HSA-eligible (e.g. $20 of a $100 pharmacy visit).
When set, dashboard totals use eligible_amount instead of the full amount.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd33ee44ff55'
down_revision: Union[str, None] = 'cc11dd22ee33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'bank_transactions',
        sa.Column('eligible_amount', sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('bank_transactions', 'eligible_amount')
