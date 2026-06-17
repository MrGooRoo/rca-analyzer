"""
Add singleton llm_settings for P17 LLM Conductor.

Revision ID: 011
Revises: 010
Create Date: 2026-06-17

Настройки управляются только admin-пользователями и задают:
- draft_model: модель для чернового RCA-анализа;
- verifier_model: дешёвый verifier для проверки/улучшения черновика;
- quality_threshold: порог confidence_avg;
- verification_scheme: disabled | threshold | always.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_model", sa.String(length=200), nullable=False),
        sa.Column("verifier_model", sa.String(length=200), nullable=True),
        sa.Column("quality_threshold", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("verification_scheme", sa.String(length=20), nullable=False, server_default="threshold"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_llm_settings_singleton"),
        sa.CheckConstraint(
            "quality_threshold >= 0.0 AND quality_threshold <= 1.0",
            name="ck_llm_settings_quality_threshold",
        ),
        sa.CheckConstraint(
            "verification_scheme IN ('disabled', 'threshold', 'always')",
            name="ck_llm_settings_verification_scheme",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO llm_settings (
                id,
                draft_model,
                verifier_model,
                quality_threshold,
                verification_scheme,
                updated_at,
                updated_by
            ) VALUES (
                1,
                'nvidia/nemotron-3-super-120b-a12b:free',
                'openai/gpt-oss-20b',
                0.70,
                'threshold',
                CURRENT_TIMESTAMP,
                NULL
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("llm_settings")
