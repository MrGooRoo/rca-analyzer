"""
Add LLM conductor provenance fields to rca_results.

Revision ID: 012
Revises: 011
Create Date: 2026-06-17

Поля позволяют видеть экономику P17:
- какая модель делала черновик;
- какая модель выполняла verifier-pass;
- сколько токенов ушло на draft/verifier;
- применялась ли верификация и почему.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rca_results", sa.Column("draft_model_used", sa.String(length=200), nullable=True))
    op.add_column("rca_results", sa.Column("verifier_model_used", sa.String(length=200), nullable=True))
    op.add_column("rca_results", sa.Column("draft_tokens_used", sa.Integer(), nullable=True))
    op.add_column("rca_results", sa.Column("verifier_tokens_used", sa.Integer(), nullable=True))
    op.add_column(
        "rca_results",
        sa.Column("verification_applied", sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.add_column("rca_results", sa.Column("verification_reason", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("rca_results", "verification_reason")
    op.drop_column("rca_results", "verification_applied")
    op.drop_column("rca_results", "verifier_tokens_used")
    op.drop_column("rca_results", "draft_tokens_used")
    op.drop_column("rca_results", "verifier_model_used")
    op.drop_column("rca_results", "draft_model_used")
