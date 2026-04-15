"""add_hsa_rules_engine

Revision ID: aabbccddee11
Revises: e5f6a7b8c9d0
Create Date: 2026-04-13 00:01:00.000000

Adds the HSA Rules Engine tables and extends bank_transactions with auto-flag
and rule_id columns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'aabbccddee11'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── hsa_rules ────────────────────────────────────────────────────────────
    op.create_table(
        'hsa_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_hsa_rules_user_id'), 'hsa_rules', ['user_id'], unique=False)

    # ── hsa_rule_conditions ──────────────────────────────────────────────────
    op.create_table(
        'hsa_rule_conditions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('field', sa.String(length=50), nullable=False),
        sa.Column('operator', sa.String(length=30), nullable=False),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['hsa_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "field IN ('counterparty_name', 'description', 'amount', 'date')",
            name='ck_hsa_rule_condition_field',
        ),
        sa.CheckConstraint(
            "operator IN ('is', 'contains', 'does_not_contain', 'is_not', 'eq', 'gt', 'lt', 'before', 'after')",
            name='ck_hsa_rule_condition_operator',
        ),
    )
    op.create_index(op.f('ix_hsa_rule_conditions_rule_id'), 'hsa_rule_conditions', ['rule_id'], unique=False)

    # ── hsa_rule_actions ─────────────────────────────────────────────────────
    op.create_table(
        'hsa_rule_actions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('action_type', sa.String(length=30), nullable=False),
        sa.Column('member_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['hsa_rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['family_members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "action_type IN ('mark_hsa', 'mark_potential', 'hide', 'assign_member')",
            name='ck_hsa_rule_action_type',
        ),
    )
    op.create_index(op.f('ix_hsa_rule_actions_rule_id'), 'hsa_rule_actions', ['rule_id'], unique=False)

    # ── bank_transactions: new columns ────────────────────────────────────────
    op.add_column(
        'bank_transactions',
        sa.Column('auto_flag', sa.String(length=20), nullable=True),
    )
    op.create_index(
        op.f('ix_bank_transactions_auto_flag'),
        'bank_transactions',
        ['auto_flag'],
        unique=False,
    )
    op.create_check_constraint(
        'ck_bank_txn_auto_flag',
        'bank_transactions',
        "auto_flag IN ('potential_hsa', 'hidden') OR auto_flag IS NULL",
    )

    op.add_column(
        'bank_transactions',
        sa.Column('rule_id', sa.UUID(), nullable=True),
    )
    op.create_index(
        op.f('ix_bank_transactions_rule_id'),
        'bank_transactions',
        ['rule_id'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_bank_transactions_rule_id',
        'bank_transactions',
        'hsa_rules',
        ['rule_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_bank_transactions_rule_id', 'bank_transactions', type_='foreignkey')
    op.drop_index(op.f('ix_bank_transactions_rule_id'), table_name='bank_transactions')
    op.drop_column('bank_transactions', 'rule_id')

    op.drop_constraint('ck_bank_txn_auto_flag', 'bank_transactions', type_='check')
    op.drop_index(op.f('ix_bank_transactions_auto_flag'), table_name='bank_transactions')
    op.drop_column('bank_transactions', 'auto_flag')

    op.drop_index(op.f('ix_hsa_rule_actions_rule_id'), table_name='hsa_rule_actions')
    op.drop_table('hsa_rule_actions')

    op.drop_index(op.f('ix_hsa_rule_conditions_rule_id'), table_name='hsa_rule_conditions')
    op.drop_table('hsa_rule_conditions')

    op.drop_index(op.f('ix_hsa_rules_user_id'), table_name='hsa_rules')
    op.drop_table('hsa_rules')