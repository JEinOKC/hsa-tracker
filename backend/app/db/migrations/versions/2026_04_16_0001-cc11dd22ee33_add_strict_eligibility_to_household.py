"""add_strict_eligibility_to_household

Revision ID: cc11dd22ee33
Revises: aabbccddee11
Create Date: 2026-04-16 00:01:00.000000

Adds strict_eligibility boolean to households table.
When true (default), HSA calculations only count transactions
that fall within the assigned member's coverage window.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc11dd22ee33'
down_revision: Union[str, None] = 'aabbccddee11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'households',
        sa.Column(
            'strict_eligibility',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
    )


def downgrade() -> None:
    op.drop_column('households', 'strict_eligibility')
