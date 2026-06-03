"""
ORM-модели (таблицы БД).

Схема:
    incidents        — входные данные инцидента
    rca_results      — результат анализа (summary, модель, токены)
    causal_nodes     — все узлы дерева причин (IC / CC / RC)
    recommendations  — корректирующие мероприятия
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class IncidentORM(Base):
    __tablename__ = "incidents"

    id:            Mapped[str]      = mapped_column(String(36), primary_key=True)
    title:         Mapped[str]      = mapped_column(String(200))
    description:   Mapped[str]      = mapped_column(Text)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location:      Mapped[str]      = mapped_column(String(200))
    incident_type: Mapped[str]      = mapped_column(String(50))
    severity:      Mapped[str]      = mapped_column(String(50))
    victims:       Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    equipment:     Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actions_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at:    Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    results: Mapped[list[RCAResultORM]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class RCAResultORM(Base):
    __tablename__ = "rca_results"

    result_id:      Mapped[str]   = mapped_column(String(36), primary_key=True)
    incident_id:    Mapped[str]   = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="CASCADE")
    )
    methodology:    Mapped[str]   = mapped_column(String(50))
    summary:        Mapped[str]   = mapped_column(Text)
    model_used:     Mapped[str]   = mapped_column(String(100))
    tokens_used:    Mapped[int]   = mapped_column(Integer)
    confidence_avg: Mapped[float] = mapped_column(Float)
    created_at:     Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    incident:      Mapped[IncidentORM]        = relationship(back_populates="results")
    causal_nodes:  Mapped[list[CausalNodeORM]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[RecommendationORM]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )


class CausalNodeORM(Base):
    __tablename__ = "causal_nodes"

    id:         Mapped[str]           = mapped_column(String(36), primary_key=True)
    result_id:  Mapped[str]           = mapped_column(
        String(36), ForeignKey("rca_results.result_id", ondelete="CASCADE")
    )
    node_id:    Mapped[str]           = mapped_column(String(20))   # IC1, CC1, RC1 …
    node_role:  Mapped[str]           = mapped_column(String(20))   # immediate | contributing | root
    text:       Mapped[str]           = mapped_column(Text)
    category:   Mapped[str]           = mapped_column(String(50))
    level:      Mapped[int]           = mapped_column(Integer)
    parent_id:  Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float]         = mapped_column(Float)

    result: Mapped[RCAResultORM] = relationship(back_populates="causal_nodes")


class RecommendationORM(Base):
    __tablename__ = "recommendations"

    id:          Mapped[str]           = mapped_column(String(36), primary_key=True)
    result_id:   Mapped[str]           = mapped_column(
        String(36), ForeignKey("rca_results.result_id", ondelete="CASCADE")
    )
    rec_id:      Mapped[str]           = mapped_column(String(20))   # R1, R2 …
    text:        Mapped[str]           = mapped_column(Text)
    priority:    Mapped[str]           = mapped_column(String(20))
    category:    Mapped[str]           = mapped_column(String(50))
    cause_id:    Mapped[str]           = mapped_column(String(20))
    responsible: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status:      Mapped[str]           = mapped_column(String(20), default="open")
    # open | in_progress | closed

    result: Mapped[RCAResultORM] = relationship(back_populates="recommendations")
