"""add_passkey_challenges

Replaces in-memory challenge storage with a DB table so that multi-container
deployments (Lambda, multi-replica servers) share WebAuthn challenge state.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-03 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'passkey_challenges',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('challenge_b64', sa.Text(), nullable=False),
        sa.Column('challenge_type', sa.String(20), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_passkey_challenges_username', 'passkey_challenges', ['username'])


def downgrade() -> None:
    op.drop_index('ix_passkey_challenges_username', table_name='passkey_challenges')
    op.drop_table('passkey_challenges')
