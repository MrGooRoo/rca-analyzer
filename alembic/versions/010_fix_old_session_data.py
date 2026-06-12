"""
Fix old sessions: backfill incident_title/description/hash from incidents table.

Revision ID: 010
Revises: 009
Create Date: 2026-06-13

Проблема: миграция 008 создала сессии из таблицы incidents, где title="—"
и description="—" (заглушки из save_result). Из-за этого incident_hash
для старых сессий равен SHA-256("—\\n—") и не совпадает с hash реальных
входных данных, поэтому старые результаты не исключаются из «похожих».

Решение:
1. Для каждой сессии с incident_title="—": пытаемся найти реальные данные
   через incident_data_json (если title там не "—").
2. Если нет — используем summary первого результата как описание.
3. Пересчитываем incident_hash для обновлённых сессий.
4. Также обновляем таблицу incidents реальными данными из сессий.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def _compute_hash(title: str, description: str) -> str:
    raw = f"{title.strip().lower()}\n{description.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_date(value) -> datetime | None:
    """Парсит дату из JSON — строка или datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    return None


def upgrade() -> None:
    conn = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=conn)
    sessions_t = meta.tables["analysis_sessions"]
    results_t = meta.tables["rca_results"]
    incidents_t = meta.tables["incidents"]

    # Получаем все сессии с placeholder-данными
    placeholder_sessions = conn.execute(
        sa.select(sessions_t).where(sessions_t.c.incident_title == "—")
    ).fetchall()

    for session in placeholder_sessions:
        session_id = session.id
        new_title = None
        new_description = None
        new_date = None
        new_location = None
        new_type = None
        new_severity = None

        # Попытка 1: извлечь из incident_data_json
        if session.incident_data_json:
            try:
                data = json.loads(session.incident_data_json)
                if data.get("title") and data["title"] != "—":
                    new_title = data["title"]
                if data.get("description") and data["description"] != "—":
                    new_description = data["description"]
                new_date = _parse_date(data.get("incident_date"))
                if data.get("location") and data["location"] not in ("", "—"):
                    new_location = data["location"]
                if data.get("incident_type") and data["incident_type"] != "unknown":
                    new_type = data["incident_type"]
                if data.get("severity") and data["severity"] != "unknown":
                    new_severity = data["severity"]
            except (json.JSONDecodeError, TypeError):
                pass

        # Попытка 2: взять summary первого результата как описание
        if not new_description:
            first_result = conn.execute(
                sa.select(results_t.c.summary)
                .where(results_t.c.session_id == session_id)
                .order_by(results_t.c.created_at.asc())
                .limit(1)
            ).fetchone()
            if first_result and first_result.summary:
                new_description = first_result.summary

        if not new_title:
            new_title = "—"

        if not new_description:
            new_description = "—"

        # Пересчитываем hash
        new_hash = _compute_hash(new_title, new_description)

        # Собираем поля для обновления сессии (только непустые)
        update_vals = {
            "incident_title": new_title,
            "incident_description": new_description,
            "incident_hash": new_hash,
        }
        if new_date is not None:
            update_vals["incident_date"] = new_date
        if new_location is not None:
            update_vals["incident_location"] = new_location
        if new_type is not None:
            update_vals["incident_type"] = new_type
        if new_severity is not None:
            update_vals["incident_severity"] = new_severity

        # Обновляем сессию
        conn.execute(
            sa.update(sessions_t)
            .where(sessions_t.c.id == session_id)
            .values(**update_vals)
        )

        # Также обновляем таблицу incidents
        incident_id_results = conn.execute(
            sa.select(results_t.c.incident_id)
            .where(results_t.c.session_id == session_id)
            .limit(1)
        ).fetchone()

        if incident_id_results:
            incident_id = incident_id_results[0]
            incident_row = conn.execute(
                sa.select(incidents_t).where(incidents_t.c.id == incident_id)
            ).fetchone()

            if incident_row and incident_row.title == "—":
                inc_update_vals = {
                    "title": new_title,
                    "description": new_description,
                }
                if new_type and incident_row.incident_type == "unknown":
                    inc_update_vals["incident_type"] = new_type
                if new_severity and incident_row.severity == "unknown":
                    inc_update_vals["severity"] = new_severity
                if new_location and incident_row.location == "—":
                    inc_update_vals["location"] = new_location

                conn.execute(
                    sa.update(incidents_t)
                    .where(incidents_t.c.id == incident_id)
                    .values(**inc_update_vals)
                )


def downgrade() -> None:
    # Нет смысла откатывать — данные были "—", теперь реальные
    pass
