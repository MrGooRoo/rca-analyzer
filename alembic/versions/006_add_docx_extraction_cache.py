"""
Add docx_extraction_cache table.

Revision ID: 006
Revises: 005
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "docx_extraction_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("extracted_fields_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("hit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_hash"),
    )
    op.create_index(
        op.f("ix_docx_extraction_cache_file_hash"),
        "docx_extraction_cache",
        ["file_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_docx_extraction_cache_file_hash"),
        table_name="docx_extraction_cache",
    )
    op.drop_table("docx_extraction_cache")
