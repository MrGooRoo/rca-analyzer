"""
Add incident_hash column to docx_extraction_cache.

Revision ID: 016
Revises: 015
Create Date: 2026-06-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "docx_extraction_cache",
        sa.Column("incident_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        op.f("ix_docx_extraction_cache_incident_hash"),
        "docx_extraction_cache",
        ["incident_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_docx_extraction_cache_incident_hash"),
        table_name="docx_extraction_cache",
    )
    op.drop_column("docx_extraction_cache", "incident_hash")
