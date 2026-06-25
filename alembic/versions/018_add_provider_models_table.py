"""Add provider_models table for scanned LLM models.

Revision ID: 018
Revises: 017
Create Date: 2026-06-25 05:50:00.000000+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "018"
down_revision = "017"

def upgrade() -> None:
    op.create_table(
        "provider_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("context_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_free", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("pricing_prompt", sa.Float(), nullable=True),
        sa.Column("pricing_completion", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_provider_models_provider_model", "provider_models", ["provider_id", "model_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_provider_models_provider_model")
    op.drop_table("provider_models")
