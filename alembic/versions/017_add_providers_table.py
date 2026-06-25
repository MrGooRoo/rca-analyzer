"""
Add providers table for LLM provider management.

Revision ID: 017
Revises: 016
Create Date: 2026-06-25 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '017'
down_revision: Union[str, None] = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'providers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('base_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table('providers')
