"""Создание исходных таблиц: incidents, rca_results, causal_nodes, recommendations.

Revision ID: 001
Revises:
Create Date: 2026-06-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id",            sa.String(36),  primary_key=True),
        sa.Column("title",         sa.String(200), nullable=False),
        sa.Column("description",   sa.Text(),      nullable=False),
        sa.Column("incident_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location",      sa.String(200), nullable=False),
        sa.Column("incident_type", sa.String(50),  nullable=False),
        sa.Column("severity",      sa.String(50),  nullable=False),
        sa.Column("victims",       sa.Integer(),   nullable=True),
        sa.Column("equipment",     sa.Text(),      nullable=True),
        sa.Column("conditions",    sa.Text(),      nullable=True),
        sa.Column("actions_taken", sa.Text(),      nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "rca_results",
        sa.Column("result_id",      sa.String(36),  primary_key=True),
        sa.Column("incident_id",    sa.String(36),  sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("methodology",    sa.String(50),  nullable=False),
        sa.Column("summary",        sa.Text(),      nullable=False),
        sa.Column("model_used",     sa.String(100), nullable=False),
        sa.Column("tokens_used",    sa.Integer(),   nullable=False),
        sa.Column("confidence_avg", sa.Float(),     nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_rca_results_incident_id", "rca_results", ["incident_id"])
    op.create_index("ix_rca_results_created_at",  "rca_results", ["created_at"])

    op.create_table(
        "causal_nodes",
        sa.Column("id",         sa.String(36), primary_key=True),
        sa.Column("result_id",  sa.String(36), sa.ForeignKey("rca_results.result_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id",    sa.String(20), nullable=False),   # IC1, CC2, RC1
        sa.Column("node_role",  sa.String(20), nullable=False),   # immediate | contributing | root
        sa.Column("text",       sa.Text(),     nullable=False),
        sa.Column("category",   sa.String(50), nullable=False),
        sa.Column("level",      sa.Integer(),  nullable=False),
        sa.Column("parent_id",  sa.String(20), nullable=True),
        sa.Column("confidence", sa.Float(),    nullable=False),
    )
    op.create_index("ix_causal_nodes_result_id", "causal_nodes", ["result_id"])

    op.create_table(
        "recommendations",
        sa.Column("id",          sa.String(36),  primary_key=True),
        sa.Column("result_id",   sa.String(36),  sa.ForeignKey("rca_results.result_id", ondelete="CASCADE"), nullable=False),
        sa.Column("rec_id",      sa.String(20),  nullable=False),   # R1, R2
        sa.Column("text",        sa.Text(),      nullable=False),
        sa.Column("priority",    sa.String(20),  nullable=False),
        sa.Column("category",    sa.String(50),  nullable=False),
        sa.Column("cause_id",    sa.String(20),  nullable=False),
        sa.Column("responsible", sa.String(200), nullable=True),
        sa.Column("status",      sa.String(20),  nullable=False, server_default="open"),
    )
    op.create_index("ix_recommendations_result_id", "recommendations", ["result_id"])
    op.create_index("ix_recommendations_status",    "recommendations", ["status"])


def downgrade() -> None:
    op.drop_table("recommendations")
    op.drop_table("causal_nodes")
    op.drop_table("rca_results")
    op.drop_table("incidents")
