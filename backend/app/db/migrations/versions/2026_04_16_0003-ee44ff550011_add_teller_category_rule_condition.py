"""add_teller_category_rule_condition

Revision ID: ee44ff550011
Revises: dd33ee44ff55
Create Date: 2026-04-16 00:03:00.000000

Expands the ck_hsa_rule_condition_field check constraint to allow
'teller_category' as a matchable field in HSA rule conditions.
This enables rules like "if teller_category is health → mark HSA".
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'ee44ff550011'
down_revision: Union[str, None] = 'dd33ee44ff55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_hsa_rule_condition_field', 'hsa_rule_conditions', type_='check')
    op.create_check_constraint(
        'ck_hsa_rule_condition_field',
        'hsa_rule_conditions',
        "field IN ('counterparty_name', 'description', 'amount', 'date', 'teller_category')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_hsa_rule_condition_field', 'hsa_rule_conditions', type_='check')
    op.create_check_constraint(
        'ck_hsa_rule_condition_field',
        'hsa_rule_conditions',
        "field IN ('counterparty_name', 'description', 'amount', 'date')",
    )
