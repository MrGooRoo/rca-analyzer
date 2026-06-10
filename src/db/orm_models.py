"""
ORM-модели (таблицы БД).

Схема:
    users                   — учётные записи пользователей
    refresh_tokens          — refresh-сессии для httpOnly cookie
    incidents               — входные данные инцидента
    rca_results             — результат анализа (summary, модель, токены)
    causal_nodes            — все узлы дерева причин (IC / CC / RC)
    recommendations         — корректирующие мероприятия
    docx_extraction_cache   — кэш результатов LLM-извлечения по хешу файла
    result_embeddings       — pgvector-эмбеддинги RCA-результатов для похожих инцидентов
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
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
from src.services.embedding_service import EMBEDDING_DIMENSION


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    refresh_tokens: Mapped[list[RefreshTokenORM]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    results: Mapped[list[RCAResultORM]] = relationship(back_populates="user")
    incidents: Mapped[list[IncidentORM]] = relationship(back_populates="user")


class RefreshTokenORM(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserORM] = relationship(back_populates="refresh_tokens")


class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(200))
    incident_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(50))
    victims: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    equipment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actions_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[Optional[UserORM]] = relationship(back_populates="incidents")
    results: Mapped[list[RCAResultORM]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class RCAResultORM(Base):
    __tablename__ = "rca_results"

    result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="CASCADE")
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    methodology: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(100))
    tokens_used: Mapped[int] = mapped_column(Integer)
    confidence_avg: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[Optional[UserORM]] = relationship(back_populates="results")
    incident: Mapped[IncidentORM] = relationship(back_populates="results")
    causal_nodes: Mapped[list[CausalNodeORM]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[RecommendationORM]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )
    embedding: Mapped[ResultEmbeddingORM | None] = relationship(
        back_populates="result", cascade="all, delete-orphan", uselist=False
    )


class CausalNodeORM(Base):
    __tablename__ = "causal_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rca_results.result_id", ondelete="CASCADE")
    )
    node_id: Mapped[str] = mapped_column(String(36))
    node_role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)

    result: Mapped[RCAResultORM] = relationship(back_populates="causal_nodes")


class RecommendationORM(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rca_results.result_id", ondelete="CASCADE")
    )
    rec_id: Mapped[str] = mapped_column(String(36))
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(50))
    cause_id: Mapped[str] = mapped_column(String(36))
    responsible: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")

    result: Mapped[RCAResultORM] = relationship(back_populates="recommendations")


class ResultEmbeddingORM(Base):
    """
    Dense-вектор RCA-результата для поиска похожих инцидентов.

    Хранится в PostgreSQL через pgvector. Вектор строится из summary,
    причин и рекомендаций результата.
    """
    __tablename__ = "result_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rca_results.result_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    result: Mapped[RCAResultORM] = relationship(back_populates="embedding")


class DocxExtractionCacheORM(Base):
    """
    Кэш результатов LLM-извлечения полей из DOCX-отчётов.

    Ключ: SHA-256 от байт файла (file_hash).
    Значение: JSON-строка с извлечёнными полями (extracted_fields_json).

    Позволяет при повторной загрузке того же файла пропустить
    все 4 параллельных LLM-запроса (~6 мин) и вернуть результат
    из БД за миллисекунды.
    """
    __tablename__ = "docx_extraction_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    extracted_fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
