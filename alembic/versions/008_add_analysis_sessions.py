"""
Add analysis_sessions table and session_id FK to rca_results.

Revision ID: 008
Revises: 007
Create Date: 2026-06-13

- Создаёт таблицу analysis_sessions для группировки анализов
  одного инцидента в логическое «исследование».
- Добавляет nullable session_id FK в rca_results.
- Backfill: для каждого существующего incident_id создаётся
  одна сессия, и все результаты с этим incident_id получают
  session_id = id этой сессии.
"""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Создаём таблицу analysis_sessions ---
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("incident_title", sa.String(200), nullable=False),
        sa.Column("incident_description", sa.Text(), nullable=False),
        sa.Column(
            "incident_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("incident_location", sa.String(200), nullable=True),
        sa.Column("incident_type", sa.String(50), nullable=True),
        sa.Column("incident_severity", sa.String(50), nullable=True),
        sa.Column("incident_data_json", sa.Text(), nullable=True),
    )

    # --- 2. Добавляем session_id в rca_results (nullable для обратной совместимости) ---
    op.add_column(
        "rca_results",
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("analysis_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_rca_results_session_id"),
        "rca_results",
        ["session_id"],
        unique=False,
    )

    # --- 3. Backfill: создаём сессии по incident_id ---
    # Для каждого уникального incident_id:
    #   - берём данные из таблицы incidents
    #   - создаём запись analysis_sessions
    #   - обновляем rca_results.session_id
    conn = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=conn)
    incidents_t = meta.tables["incidents"]
    results_t = meta.tables["rca_results"]

    # Получаем все уникальные incident_id из rca_results
    incident_ids = conn.execute(
        sa.select(results_t.c.incident_id).distinct()
    ).fetchall()

    for (incident_id,) in incident_ids:
        # Берём данные инцидента
        inc_row = conn.execute(
            sa.select(incidents_t).where(incidents_t.c.id == incident_id)
        ).fetchone()

        if inc_row is None:
            continue

        # Берём user_id и created_at из первого результата
        first_result = conn.execute(
            sa.select(results_t)
            .where(results_t.c.incident_id == incident_id)
            .order_by(results_t.c.created_at.asc())
            .limit(1)
        ).fetchone()

        session_id = str(uuid.uuid4())
        session_user_id = first_result.user_id if first_result else None
        # created_at = дата самого раннего результата
        session_created_at = first_result.created_at if first_result else None

        # Формируем incident_data_json из данных инцидента
        incident_data = {
            "title": inc_row.title or "—",
            "description": inc_row.description or "—",
            "incident_date": inc_row.incident_date.isoformat() if inc_row.incident_date else None,
            "location": inc_row.location or "",
            "incident_type": inc_row.incident_type or "unknown",
            "severity": inc_row.severity or "unknown",
        }
        if inc_row.victims is not None:
            incident_data["victims"] = inc_row.victims
        if inc_row.equipment:
            incident_data["equipment"] = inc_row.equipment
        if inc_row.conditions:
            incident_data["conditions"] = inc_row.conditions
        if inc_row.actions_taken:
            incident_data["actions_taken"] = inc_row.actions_taken

        conn.execute(
            sa.insert(meta.tables["analysis_sessions"]).values(
                id=session_id,
                created_at=session_created_at,
                user_id=session_user_id,
                incident_title=inc_row.title or "—",
                incident_description=inc_row.description or "—",
                incident_date=inc_row.incident_date,
                incident_location=inc_row.location,
                incident_type=inc_row.incident_type,
                incident_severity=inc_row.severity,
                incident_data_json=json.dumps(incident_data, ensure_ascii=False, default=str),
            )
        )

        # Обновляем все результаты с этим incident_id
        conn.execute(
            sa.update(results_t)
            .where(results_t.c.incident_id == incident_id)
            .values(session_id=session_id)
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_rca_results_session_id"), table_name="rca_results")
    op.drop_column("rca_results", "session_id")
    op.drop_table("analysis_sessions")
