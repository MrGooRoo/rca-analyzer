"""add balance column + user_transactions table

Revision ID: 020
Revises: 019
Create Date: 2026-06-25 13:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: str | None = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_transactions table
    op.create_table(
        "user_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("reference_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    # balance column on users
    op.add_column(
        "users",
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0.00")),
    )


def downgrade() -> None:
    op.drop_column("users", "balance")
    op.drop_table("user_transactions")
