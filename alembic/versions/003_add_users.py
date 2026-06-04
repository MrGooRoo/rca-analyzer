"""Добавить таблицу users и user_id в rca_results / incidents.

Revision ID: 003
Revises: 002
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id",            sa.String(36),  primary_key=True),
        sa.Column("email",         sa.String(200), nullable=False, unique=True),
        sa.Column("display_name",  sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # nullable=True, чтобы не сломать существующие строки
    op.add_column("incidents",   sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("rca_results", sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_incidents_user_id",   "incidents",   ["user_id"])
    op.create_index("ix_rca_results_user_id", "rca_results", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_rca_results_user_id", "rca_results")
    op.drop_index("ix_incidents_user_id",   "incidents")
    op.drop_column("rca_results", "user_id")
    op.drop_column("incidents",   "user_id")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
