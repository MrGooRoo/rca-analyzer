"""Синхронизация длин полей incident/analysis_sessions с Pydantic-валидацией.

Pydantic (src/domain/models.py):
  title: max_length=500, location: max_length=500, incident_type: max_length=100

DB (миграция 001):
  incidents.title:         String(200)  → String(500)
  incidents.location:      String(200)  → String(500)
  incidents.incident_type: String(50)   → String(100)

DB (миграция 008):
  analysis_sessions.incident_title:    String(200) → String(500)
  analysis_sessions.incident_location: String(200) → String(500)
  analysis_sessions.incident_type:     String(50)  → String(100)

Риск без миграции: StringDataRightTruncationError при PostgreSQL,
когда Pydantic пропускает данные, а СУБД их обрезает.

Revision ID: 015
Revises: 014
Create Date: 2026-06-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # incidents: String(200) → String(500) для title и location
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.alter_column("title", type_=sa.String(500), existing_type=sa.String(200))
        batch_op.alter_column("location", type_=sa.String(500), existing_type=sa.String(200))
        batch_op.alter_column("incident_type", type_=sa.String(100), existing_type=sa.String(50))

    # analysis_sessions: String(200) → String(500) для incident_title и incident_location
    with op.batch_alter_table("analysis_sessions", schema=None) as batch_op:
        batch_op.alter_column("incident_title", type_=sa.String(500), existing_type=sa.String(200))
        batch_op.alter_column("incident_location", type_=sa.String(500), existing_type=sa.String(200))
        batch_op.alter_column("incident_type", type_=sa.String(100), existing_type=sa.String(50))


def downgrade() -> None:
    with op.batch_alter_table("analysis_sessions", schema=None) as batch_op:
        batch_op.alter_column("incident_type", type_=sa.String(50), existing_type=sa.String(100))
        batch_op.alter_column("incident_location", type_=sa.String(200), existing_type=sa.String(500))
        batch_op.alter_column("incident_title", type_=sa.String(200), existing_type=sa.String(500))

    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.alter_column("incident_type", type_=sa.String(50), existing_type=sa.String(100))
        batch_op.alter_column("location", type_=sa.String(200), existing_type=sa.String(500))
        batch_op.alter_column("title", type_=sa.String(200), existing_type=sa.String(500))
