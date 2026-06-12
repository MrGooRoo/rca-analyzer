"""
Add incident_hash to analysis_sessions for deduplication of similar incidents.

Revision ID: 009
Revises: 008
Create Date: 2026-06-13

- Добавляет колонку incident_hash (SHA-256 от title+description) в analysis_sessions.
- Backfill: вычисляет hash для всех существующих сессий.
- Индекс по incident_hash для быстрого поиска при исключении дубликатов.
"""

from __future__ import annotations

import hashlib

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Добавляем колонку incident_hash ---
    op.add_column(
        "analysis_sessions",
        sa.Column("incident_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        op.f("ix_analysis_sessions_incident_hash"),
        "analysis_sessions",
        ["incident_hash"],
        unique=False,
    )

    # --- 2. Backfill: вычисляем hash для существующих сессий ---
    conn = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=conn)
    sessions_t = meta.tables["analysis_sessions"]

    rows = conn.execute(
        sa.select(sessions_t.c.id, sessions_t.c.incident_title, sessions_t.c.incident_description)
    ).fetchall()

    for row_id, title, description in rows:
        raw = f"{(title or '').strip().lower()}\n{(description or '').strip().lower()}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        conn.execute(
            sa.update(sessions_t).where(sessions_t.c.id == row_id).values(incident_hash=h)
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_sessions_incident_hash"), table_name="analysis_sessions")
    op.drop_column("analysis_sessions", "incident_hash")
