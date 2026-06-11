"""Расширение VARCHAR-полей в causal_nodes и recommendations.

Проблемы, которые исправляет эта миграция:
1. causal_nodes.node_id   VARCHAR(20) → VARCHAR(36)  — UUID не влезал (36 символов)
2. causal_nodes.parent_id VARCHAR(20) → VARCHAR(36)  — UUID не влезал
3. causal_nodes.category  VARCHAR(50) → VARCHAR(100) — «небезопасные действия» = 21 символ,
                                                        «предшествующие условия» = 24, запас на будущее
4. recommendations.rec_id   VARCHAR(20) → VARCHAR(36) — аналогично node_id
5. recommendations.cause_id VARCHAR(20) → VARCHAR(36) — UUID не влезал

Revision ID: 002
Revises: 001
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # causal_nodes
    op.alter_column(
        "causal_nodes", "node_id",
        existing_type=sa.String(20),
        type_=sa.String(36),
        existing_nullable=False,
    )
    op.alter_column(
        "causal_nodes", "parent_id",
        existing_type=sa.String(20),
        type_=sa.String(36),
        existing_nullable=True,
    )
    op.alter_column(
        "causal_nodes", "category",
        existing_type=sa.String(50),
        type_=sa.String(100),
        existing_nullable=False,
    )

    # recommendations
    op.alter_column(
        "recommendations", "rec_id",
        existing_type=sa.String(20),
        type_=sa.String(36),
        existing_nullable=False,
    )
    op.alter_column(
        "recommendations", "cause_id",
        existing_type=sa.String(20),
        type_=sa.String(36),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "recommendations", "cause_id",
        existing_type=sa.String(36),
        type_=sa.String(20),
        existing_nullable=False,
    )
    op.alter_column(
        "recommendations", "rec_id",
        existing_type=sa.String(36),
        type_=sa.String(20),
        existing_nullable=False,
    )
    op.alter_column(
        "causal_nodes", "category",
        existing_type=sa.String(100),
        type_=sa.String(50),
        existing_nullable=False,
    )
    op.alter_column(
        "causal_nodes", "parent_id",
        existing_type=sa.String(36),
        type_=sa.String(20),
        existing_nullable=True,
    )
    op.alter_column(
        "causal_nodes", "node_id",
        existing_type=sa.String(36),
        type_=sa.String(20),
        existing_nullable=False,
    )
