"""Add model_preferences JSONB column to users table.

Revision ID: 019
Revises: 018
Create Date: 2026-06-25 06:15:00.000000+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"

def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("model_preferences", postgresql.JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("users", "model_preferences")
