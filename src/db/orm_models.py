"""
ORM-модели (таблицы БД).

Схема:
    users                   — учётные записи пользователей
    refresh_tokens          — refresh-сессии для httpOnly cookie
    incidents               — входные данные инцидента
    analysis_sessions       — исследование (группа анализов одного инцидента)
    rca_results             — результат анализа (summary, модель, токены)
    causal_nodes            — все узлы дерева причин (IC / CC / RC)
    recommendations         — корректирующие мероприятия
    docx_extraction_cache   — кэш результатов LLM-извлечения по хешу файла
    result_embeddings       — pgvector-эмбеддинги RCA-результатов для похожих инцидентов
    llm_settings            — singleton admin-настройки LLM Conductor (P17)
    providers               — провайдеры LLM (OpenRouter, OpenModel и т.д.)
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text as sa_text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.services.embedding_service import EMBEDDING_DIMENSION  # noqa: E402


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    model_preferences: Mapped[dict | None] = mapped_column(
        postgresql.JSONB, nullable=True, server_default=sa_text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Account lockout: защита от brute force
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    refresh_tokens: Mapped[list[RefreshTokenORM]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    results: Mapped[list[RCAResultORM]] = relationship(back_populates="user")
    incidents: Mapped[list[IncidentORM]] = relationship(back_populates="user")
    sessions: Mapped[list[AnalysisSessionORM]] = relationship(back_populates="user")


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
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserORM] = relationship(back_populates="refresh_tokens")


class LLMSettingsORM(Base):
    """Singleton admin settings for P17 LLM Conductor."""

    __tablename__ = "llm_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_llm_settings_singleton"),
        CheckConstraint(
            "quality_threshold >= 0.0 AND quality_threshold <= 1.0",
            name="ck_llm_settings_quality_threshold",
        ),
        CheckConstraint(
            "verification_scheme IN ('disabled', 'threshold', 'always')",
            name="ck_llm_settings_verification_scheme",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    draft_model: Mapped[str] = mapped_column(String(200), nullable=False)
    verifier_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quality_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.70)
    verification_scheme: Mapped[str] = mapped_column(
        String(20), nullable=False, default="threshold"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(500))
    incident_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(50))
    victims: Mapped[int | None] = mapped_column(Integer, nullable=True)
    equipment: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    actions_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[UserORM | None] = relationship(back_populates="incidents")
    results: Mapped[list[RCAResultORM]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class AnalysisSessionORM(Base):
    """
    Исследование — логическая группа анализов одного инцидента.

    Для одиночного анализа — одна сессия с одним результатом.
    Для сравнения методик — одна сессия с N результатами (по одной на методику).
    Заменяет неявную группировку по incident_id явным FK.
    """
    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Ключевые поля инцидента для быстрого доступа (как в incidents)
    incident_title: Mapped[str] = mapped_column(String(500), nullable=False)
    incident_description: Mapped[str] = mapped_column(Text, nullable=False)
    incident_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    incident_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    incident_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    incident_severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Полный IncidentInput как JSON — для сохранения всех полей
    incident_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SHA-256 отпечаток входных данных (title+description) — для исключения
    # повторных анализов того же инцидента из «похожих».
    # Один и тот же инцидент → одинаковый hash → не показываем как «похожий».
    incident_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    user: Mapped[UserORM | None] = relationship(back_populates="sessions")
    results: Mapped[list[RCAResultORM]] = relationship(back_populates="session")


class RCAResultORM(Base):
    __tablename__ = "rca_results"

    result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="CASCADE")
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("analysis_sessions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    methodology: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(100))
    tokens_used: Mapped[int] = mapped_column(Integer)
    confidence_avg: Mapped[float] = mapped_column(Float)
    # P17 LLM Conductor provenance (nullable for historical rows)
    draft_model_used: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verifier_model_used: Mapped[str | None] = mapped_column(String(200), nullable=True)
    draft_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verifier_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verification_applied: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, server_default="false"
    )
    verification_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[UserORM | None] = relationship(back_populates="results")
    incident: Mapped[IncidentORM] = relationship(back_populates="results")
    session: Mapped[AnalysisSessionORM | None] = relationship(back_populates="results")
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
    # LLM-generated ids may be longer than UUIDs (e.g. "imm-<uuid>", "root-<uuid>").
    node_id: Mapped[str] = mapped_column(String(200))
    node_role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)

    result: Mapped[RCAResultORM] = relationship(back_populates="causal_nodes")


class RecommendationORM(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rca_results.result_id", ondelete="CASCADE")
    )
    # LLM-generated recommendation/cause ids may include prefixes and exceed UUID length.
    rec_id: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(50))
    cause_id: Mapped[str] = mapped_column(String(200))
    responsible: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="open")

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
    incident_hash — SHA-256 от title+description для дедупликации
    по содержимому (разные файлы с тем же инцидентом).

    Позволяет при повторной загрузке того же файла пропустить
    все 4 параллельных LLM-запроса (~6 мин) и вернуть результат
    из БД за миллисекунды.
    """
    __tablename__ = "docx_extraction_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    incident_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    extracted_fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProviderORM(Base):
    """Провайдер LLM (OpenRouter, OpenModel и т.д.)."""
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    models: Mapped[list[ProviderModelORM]] = relationship(back_populates="provider", cascade="all, delete-orphan")


class ProviderModelORM(Base):
    """Модель LLM, считанная с каталога провайдера."""
    __tablename__ = "provider_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("providers.id"), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    context_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pricing_prompt: Mapped[float | None] = mapped_column(Float, nullable=True)
    pricing_completion: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    provider: Mapped[ProviderORM] = relationship(back_populates="models")
