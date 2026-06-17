"""
Expand LLM-generated node/recommendation id columns.

Revision ID: 013
Revises: 012
Create Date: 2026-06-17

Некоторые LLM-ответы используют id с префиксами поверх UUID:
- imm-11111111-1111-1111-1111-111111111111
- contrib-22222222-2222-2222-2222-222222222222
- r1111111-r111-r111-r111-r111111111111

Старые VARCHAR(36) подходят только для чистого UUID и приводят к
StringDataRightTruncationError при сохранении результатов multi-analysis.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "causal_nodes",
        "node_id",
        existing_type=sa.String(length=36),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.alter_column(
        "causal_nodes",
        "parent_id",
        existing_type=sa.String(length=36),
        type_=sa.String(length=200),
        existing_nullable=True,
    )
    op.alter_column(
        "recommendations",
        "rec_id",
        existing_type=sa.String(length=36),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.alter_column(
        "recommendations",
        "cause_id",
        existing_type=sa.String(length=36),
        type_=sa.String(length=200),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Может завершиться ошибкой, если в таблицах уже есть значения длиннее 36 символов.
    op.alter_column(
        "recommendations",
        "cause_id",
        existing_type=sa.String(length=200),
        type_=sa.String(length=36),
        existing_nullable=False,
    )
    op.alter_column(
        "recommendations",
        "rec_id",
        existing_type=sa.String(length=200),
        type_=sa.String(length=36),
        existing_nullable=False,
    )
    op.alter_column(
        "causal_nodes",
        "parent_id",
        existing_type=sa.String(length=200),
        type_=sa.String(length=36),
        existing_nullable=True,
    )
    op.alter_column(
        "causal_nodes",
        "node_id",
        existing_type=sa.String(length=200),
        type_=sa.String(length=36),
        existing_nullable=False,
    )
