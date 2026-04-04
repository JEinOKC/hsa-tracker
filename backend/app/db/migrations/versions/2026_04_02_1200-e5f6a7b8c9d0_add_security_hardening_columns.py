"""add_security_hardening_columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-02 12:00:00.000000

Adds columns to support:
- Account lockout after repeated failed logins (users table)
- TOTP replay-attack prevention (user_totp table)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Account lockout columns on users
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))

    # TOTP replay-prevention columns on user_totp
    op.add_column('user_totp', sa.Column('last_used_code', sa.String(length=10), nullable=True))
    op.add_column('user_totp', sa.Column('last_used_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_totp', 'last_used_at')
    op.drop_column('user_totp', 'last_used_code')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
