"""
Add account lockout fields (failed_login_attempts, locked_until).

Revision ID: 014
Revises: 013
Create Date: 2026-06-22

Защита от brute force: после MAX_FAILED_LOGIN_ATTEMPTS неудачных попыток
входа аккаунт блокируется на LOCKOUT_MINUTES минут. Новые поля:
- failed_login_attempts (Integer, default 0)
- locked_until (DateTime, nullable)
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
