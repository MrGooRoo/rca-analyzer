"""
Add result_embeddings table for similar incident search (pgvector).

Revision ID: 007
Revises: 006
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op
from src.services.embedding_service import EMBEDDING_DIMENSION

# revision identifiers
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Требуется docker image с установленным расширением pgvector
    # (см. docker-compose.yml: pgvector/pgvector:pg16).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "result_embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(36),
            sa.ForeignKey("rca_results.result_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_result_embeddings_result_id"),
        "result_embeddings",
        ["result_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_result_embeddings_model_name"),
        "result_embeddings",
        ["model_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_result_embeddings_created_at"),
        "result_embeddings",
        ["created_at"],
        unique=False,
    )

    # Индекс cosine ANN. Для небольших объёмов данных PostgreSQL может выбрать seq scan,
    # но при росте истории индекс ускорит ORDER BY embedding <=> query.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_result_embeddings_embedding_ivfflat "
        "ON result_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_result_embeddings_embedding_ivfflat")
    op.drop_index(op.f("ix_result_embeddings_created_at"), table_name="result_embeddings")
    op.drop_index(op.f("ix_result_embeddings_model_name"), table_name="result_embeddings")
    op.drop_index(op.f("ix_result_embeddings_result_id"), table_name="result_embeddings")
    op.drop_table("result_embeddings")
