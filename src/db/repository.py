"""
RCA Repository — единственная точка доступа к БД.
"""

from __future__ import annotations

import hashlib
import inspect
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.orm_models import (
    AnalysisSessionORM,
    CausalNodeORM,
    IncidentORM,
    RCAResultORM,
    RecommendationORM,
    ResultEmbeddingORM,
)
from src.domain.models import (
    AnalysisSession,
    CauseNode,
    RCAResult,
    Recommendation,
    SimilarIncident,
)
from src.integrations.embeddings.protocol import EmbeddingFn
from src.services.embedding_service import (
    EmbeddingService,
    EmbeddingServiceError,
    LocalHashEmbeddingService,
    build_result_embedding_text,
    cosine_similarity,
    get_embedding_service,
)

logger = logging.getLogger(__name__)


def compute_incident_hash(title: str, description: str) -> str:
    """
    SHA-256 отпечаток инцидента по title + description.

    Один и тот же инцидент, проанализированный разными методиками
    или в разное время, получает одинаковый hash. Это позволяет
    исключать повторные анализы из результатов «похожих инцидентов».
    """
    raw = f"{title.strip().lower()}\n{description.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _get_incident_hash_for_result(
    session: AsyncSession, result_id: str | None, incident_id: str | None,
) -> str | None:
    """
    Получить incident_hash сессии, к которой принадлежит результат.

    Используется для исключения повторных анализов того же инцидента
    из результатов поиска похожих.
    """
    if not result_id and not incident_id:
        return None
    stmt = (
        select(AnalysisSessionORM.incident_hash)
        .join(RCAResultORM, RCAResultORM.session_id == AnalysisSessionORM.id)
    )
    if result_id:
        stmt = stmt.where(RCAResultORM.result_id == result_id)
    elif incident_id:
        stmt = stmt.where(RCAResultORM.incident_id == incident_id)
    stmt = stmt.limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    return row


class RCARepository:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        *,
        embed_fn: EmbeddingFn | None = None,
        auto_commit: bool = True,
    ) -> None:
        self._session = session
        self._embed_fn = embed_fn
        self._embeddings = embedding_service or get_embedding_service()
        # Локальный фолбэк, если внешний embedding-провайдер недоступен.
        self._fallback_embeddings = LocalHashEmbeddingService()
        self._auto_commit = auto_commit

    async def _embed(self, text: str) -> tuple[list[float], str, int]:
        """
        Построить embedding текущим провайдером (sync или async).

        Если embed_fn передан (из use-case слоя), использует его напрямую.
        Иначе — старый путь: embedding_service → fallback на LocalHashEmbeddingService.
        """
        if self._embed_fn is not None:
            return await self._embed_fn(text)

        try:
            result = self._embeddings.embed(text)
            if inspect.isawaitable(result):
                result = await result
            return list(result), self._embeddings.model_name, self._embeddings.dimension
        except EmbeddingServiceError as exc:
            if self._embeddings is self._fallback_embeddings:
                raise
            logger.warning(
                "[Embeddings] провайдер %s недоступен (%s) — фолбэк на %s",
                self._embeddings.model_name, exc, self._fallback_embeddings.model_name,
            )
            vector = self._fallback_embeddings.embed(text)
            return (
                vector,
                self._fallback_embeddings.model_name,
                self._fallback_embeddings.dimension,
            )

    async def _session_call(self, method_name: str, *args) -> None:
        """
        В SQLAlchemy AsyncSession методы add/add_all синхронные, но в тестах
        с AsyncMock они становятся awaitable. Этот helper поддерживает оба режима.
        """
        result = getattr(self._session, method_name)(*args)
        if inspect.isawaitable(result):
            await result

    # ------------------------------------------------------------------
    # Запись
    # ------------------------------------------------------------------

    async def save_result(
        self,
        result: RCAResult,
        user_id: str | None = None,
        session_id: str | None = None,
        incident_title: str | None = None,
        incident_description: str | None = None,
        incident_date: datetime | None = None,
        incident_location: str | None = None,
        incident_type: str | None = None,
        incident_severity: str | None = None,
    ) -> None:
        existing_incident = await self._session.get(IncidentORM, result.incident_id)
        if existing_incident is None:
            incident_orm = IncidentORM(
                id=result.incident_id,
                title=incident_title or "—",
                description=incident_description or "—",
                incident_date=incident_date or result.created_at,
                location=incident_location or "—",
                incident_type=incident_type or "unknown",
                severity=incident_severity or "unknown",
                user_id=user_id,
            )
            await self._session_call("add", incident_orm)

        rca_orm = RCAResultORM(
            result_id=result.result_id,
            incident_id=result.incident_id,
            session_id=session_id,
            user_id=user_id,
            methodology=result.methodology.value,
            summary=result.summary,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
            confidence_avg=result.confidence_avg,
            draft_model_used=result.draft_model_used,
            verifier_model_used=result.verifier_model_used,
            draft_tokens_used=result.draft_tokens_used,
            verifier_tokens_used=result.verifier_tokens_used,
            verification_applied=result.verification_applied,
            verification_reason=result.verification_reason,
            created_at=result.created_at,
        )
        await self._session_call("add", rca_orm)

        def _nodes(nodes: list[CauseNode], role: str) -> list[CausalNodeORM]:
            return [
                CausalNodeORM(
                    id=str(uuid.uuid4()),
                    result_id=result.result_id,
                    node_id=node.id,
                    node_role=role,
                    text=node.text,
                    category=node.category,
                    level=node.level,
                    parent_id=node.parent_id,
                    confidence=node.confidence,
                )
                for node in nodes
            ]

        await self._session_call("add_all", _nodes(result.immediate_causes, "immediate"))
        await self._session_call("add_all", _nodes(result.contributing_causes, "contributing"))
        await self._session_call("add_all", _nodes(result.root_causes, "root"))

        for rec in result.recommendations:
            await self._session_call(
                "add",
                RecommendationORM(
                    id=str(uuid.uuid4()),
                    result_id=result.result_id,
                    rec_id=rec.id,
                    text=rec.text,
                    priority=rec.priority,
                    category=rec.category,
                    cause_id=rec.cause_id,
                    responsible=rec.responsible,
                ),
            )

        source_text = build_result_embedding_text(result)
        vector, model_name, dimension = await self._embed(source_text)
        await self._session_call(
            "add",
            ResultEmbeddingORM(
                id=str(uuid.uuid4()),
                result_id=result.result_id,
                model_name=model_name,
                dimension=dimension,
                embedding=vector,
                source_text=source_text,
            ),
        )

        if self._auto_commit:
            await self._session.commit()

    # ------------------------------------------------------------------
    # Чтение
    # ------------------------------------------------------------------

    async def get_result(self, result_id: str) -> RCAResult | None:
        stmt = (
            select(RCAResultORM)
            .where(RCAResultORM.result_id == result_id)
            .options(
                selectinload(RCAResultORM.causal_nodes),
                selectinload(RCAResultORM.recommendations),
                selectinload(RCAResultORM.user),
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _orm_to_domain(row) if row else None

    async def list_results(
        self,
        user_id: str | None = None,
        incident_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RCAResult]:
        stmt = (
            select(RCAResultORM)
            .options(
                selectinload(RCAResultORM.causal_nodes),
                selectinload(RCAResultORM.recommendations),
                selectinload(RCAResultORM.user),
            )
            .order_by(RCAResultORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if user_id:
            stmt = stmt.where(RCAResultORM.user_id == user_id)
        if incident_id:
            stmt = stmt.where(RCAResultORM.incident_id == incident_id)

        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_domain(r) for r in rows]

    async def backfill_missing_embeddings(
        self,
        user_id: str | None = None,
        limit: int = 100,
    ) -> int:
        """
        Доиндексировать RCA-результаты без embedding текущей модели.

        Покрывает два случая:
        1. embedding отсутствует вовсе (старые записи);
        2. embedding построен другой моделью (сменили EMBEDDINGS_PROVIDER) —
           старая запись заменяется новой.

        Если внешний провайдер недоступен и сработал фолбэк на локальную модель,
        записи «другой модели» не перезаписываются (чтобы не было churn
        local → external → local при перебоях сети).
        """
        target_model = self._embeddings.model_name
        stmt = (
            select(RCAResultORM, ResultEmbeddingORM)
            .outerjoin(ResultEmbeddingORM, ResultEmbeddingORM.result_id == RCAResultORM.result_id)
            .where(
                (ResultEmbeddingORM.result_id.is_(None))
                | (ResultEmbeddingORM.model_name != target_model)
            )
            .options(
                selectinload(RCAResultORM.causal_nodes),
                selectinload(RCAResultORM.recommendations),
            )
            .order_by(RCAResultORM.created_at.desc())
            .limit(limit)
        )
        if user_id:
            stmt = stmt.where(RCAResultORM.user_id == user_id)

        rows = (await self._session.execute(stmt)).all()
        updated = 0
        for row, existing_embedding in rows:
            source_text = _embedding_text_from_orm(row)
            vector, model_name, dimension = await self._embed(source_text)

            if existing_embedding is not None:
                # Сработал фолбэк и вектор той же модели уже есть — не трогаем.
                if existing_embedding.model_name == model_name:
                    continue
                existing_embedding.model_name = model_name
                existing_embedding.dimension = dimension
                existing_embedding.embedding = vector
                existing_embedding.source_text = source_text
            else:
                await self._session_call(
                    "add",
                    ResultEmbeddingORM(
                        id=str(uuid.uuid4()),
                        result_id=row.result_id,
                        model_name=model_name,
                        dimension=dimension,
                        embedding=vector,
                        source_text=source_text,
                    ),
                )
            updated += 1

        if updated:
            if self._auto_commit:
                await self._session.commit()
        return updated

    async def find_similar_incidents(
        self,
        text: str,
        user_id: str | None = None,
        limit: int = 5,
        threshold: float = 0.15,
        exclude_result_id: str | None = None,
        exclude_incident_id: str | None = None,
        exclude_incident_hash: str | None = None,
    ) -> list[SimilarIncident]:
        """Найти top-N похожих инцидентов по cosine similarity.

        exclude_incident_hash: если задан, исключить результаты из сессий
        с таким же hash (повторные анализы того же инцидента).
        """
        # Автоматически определяем hash сессии текущего результата
        if not exclude_incident_hash and (exclude_result_id or exclude_incident_id):
            exclude_incident_hash = await _get_incident_hash_for_result(
                self._session, exclude_result_id, exclude_incident_id,
            )

        query_embedding, query_model, _ = await self._embed(text)
        dialect = self._dialect_name()

        if dialect == "postgresql":
            return await self._find_similar_incidents_pgvector(
                query_embedding=query_embedding,
                query_model=query_model,
                user_id=user_id,
                limit=limit,
                threshold=threshold,
                exclude_result_id=exclude_result_id,
                exclude_incident_id=exclude_incident_id,
                exclude_incident_hash=exclude_incident_hash,
            )

        return await self._find_similar_incidents_python(
            query_embedding=query_embedding,
            query_model=query_model,
            user_id=user_id,
            limit=limit,
            threshold=threshold,
            exclude_result_id=exclude_result_id,
            exclude_incident_id=exclude_incident_id,
            exclude_incident_hash=exclude_incident_hash,
        )

    async def _find_similar_incidents_pgvector(
        self,
        query_embedding: list[float],
        query_model: str,
        user_id: str | None,
        limit: int,
        threshold: float,
        exclude_result_id: str | None,
        exclude_incident_id: str | None,
        exclude_incident_hash: str | None,
    ) -> list[SimilarIncident]:
        distance = ResultEmbeddingORM.embedding.cosine_distance(query_embedding)
        stmt = (
            select(RCAResultORM, distance.label("distance"))
            .join(ResultEmbeddingORM, ResultEmbeddingORM.result_id == RCAResultORM.result_id)
            .where(ResultEmbeddingORM.model_name == query_model)
            .options(
                selectinload(RCAResultORM.causal_nodes),
                selectinload(RCAResultORM.recommendations),
                selectinload(RCAResultORM.user),
                selectinload(RCAResultORM.session),
            )
            .order_by(distance.asc(), RCAResultORM.created_at.desc())
            .limit(max(limit * 3, limit))
        )
        if user_id:
            stmt = stmt.where(RCAResultORM.user_id == user_id)
        if exclude_result_id:
            stmt = stmt.where(RCAResultORM.result_id != exclude_result_id)
        if exclude_incident_id:
            stmt = stmt.where(RCAResultORM.incident_id != exclude_incident_id)
        # Исключаем результаты из сессий с таким же incident_hash
        # (повторные анализы того же инцидента — не «похожие»)
        if exclude_incident_hash:
            stmt = stmt.where(
                RCAResultORM.session_id.is_(None)
                | (
                    RCAResultORM.session_id.in_(
                        select(AnalysisSessionORM.id).where(
                            AnalysisSessionORM.incident_hash != exclude_incident_hash,
                            # Также исключаем старые сессии с placeholder-заголовком "—"
                            # (мы не можем определить, тот же это инцидент или нет,
                            # поэтому лучше скрыть, чем показывать как «похожие»)
                            AnalysisSessionORM.incident_title != "—",
                        )
                    )
                )
            )

        rows = (await self._session.execute(stmt)).all()
        similar: list[SimilarIncident] = []
        seen_incidents: set[str] = set()

        for row, distance_value in rows:
            if row.incident_id in seen_incidents:
                continue
            distance_num = 1.0 if distance_value is None else float(distance_value)
            similarity = 1.0 - distance_num
            if similarity < threshold:
                continue
            similar.append(_orm_to_similar(row, similarity=similarity))
            seen_incidents.add(row.incident_id)
            if len(similar) >= limit:
                break

        return similar

    async def _find_similar_incidents_python(
        self,
        query_embedding: list[float],
        query_model: str,
        user_id: str | None,
        limit: int,
        threshold: float,
        exclude_result_id: str | None,
        exclude_incident_id: str | None,
        exclude_incident_hash: str | None,
    ) -> list[SimilarIncident]:
        stmt = (
            select(RCAResultORM, ResultEmbeddingORM)
            .join(ResultEmbeddingORM, ResultEmbeddingORM.result_id == RCAResultORM.result_id)
            .where(ResultEmbeddingORM.model_name == query_model)
            .options(
                selectinload(RCAResultORM.causal_nodes),
                selectinload(RCAResultORM.recommendations),
                selectinload(RCAResultORM.user),
                selectinload(RCAResultORM.session),
            )
            .order_by(RCAResultORM.created_at.desc())
            .limit(500)
        )
        if user_id:
            stmt = stmt.where(RCAResultORM.user_id == user_id)
        if exclude_result_id:
            stmt = stmt.where(RCAResultORM.result_id != exclude_result_id)
        if exclude_incident_id:
            stmt = stmt.where(RCAResultORM.incident_id != exclude_incident_id)
        if exclude_incident_hash:
            stmt = stmt.where(
                RCAResultORM.session_id.is_(None)
                | (
                    RCAResultORM.session_id.in_(
                        select(AnalysisSessionORM.id).where(
                            AnalysisSessionORM.incident_hash != exclude_incident_hash,
                            AnalysisSessionORM.incident_title != "—",
                        )
                    )
                )
            )

        rows = (await self._session.execute(stmt)).all()
        scored: list[tuple[RCAResultORM, float]] = []
        for row, embedding in rows:
            similarity = cosine_similarity(query_embedding, list(embedding.embedding))
            if similarity >= threshold:
                scored.append((row, similarity))

        scored.sort(key=lambda item: (item[1], item[0].created_at), reverse=True)

        similar: list[SimilarIncident] = []
        seen_incidents: set[str] = set()
        for row, similarity in scored:
            if row.incident_id in seen_incidents:
                continue
            similar.append(_orm_to_similar(row, similarity=similarity))
            seen_incidents.add(row.incident_id)
            if len(similar) >= limit:
                break
        return similar

    def _dialect_name(self) -> str:
        try:
            return self._session.get_bind().dialect.name
        except Exception:
            return ""

    async def delete_result(self, result_id: str) -> bool:
        """Удалить результат анализа и все связанные записи (каскадно)."""
        row = await self._session.get(RCAResultORM, result_id)
        if row is None:
            return False
        await self._session.delete(row)
        if self._auto_commit:
            await self._session.commit()
        return True

    async def update_recommendation_status(
        self, result_id: str, rec_id: str, status: str
    ) -> bool:
        stmt = select(RecommendationORM).where(
            RecommendationORM.result_id == result_id,
            RecommendationORM.rec_id == rec_id,
        )
        rec = (await self._session.execute(stmt)).scalar_one_or_none()
        if rec is None:
            return False
        rec.status = status
        if self._auto_commit:
            await self._session.commit()
        return True

    # ------------------------------------------------------------------
    # Сессии исследований (analysis_sessions)
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        user_id: str | None = None,
        incident_title: str,
        incident_description: str,
        incident_date: datetime | None = None,
        incident_location: str | None = None,
        incident_type: str | None = None,
        incident_severity: str | None = None,
        incident_data_json: str | None = None,
    ) -> AnalysisSessionORM:
        """Создать новую запись analysis_sessions и вернуть ORM-объект."""
        incident_hash = compute_incident_hash(incident_title, incident_description)
        session_orm = AnalysisSessionORM(
            id=str(uuid.uuid4()),
            user_id=user_id,
            incident_title=incident_title,
            incident_description=incident_description,
            incident_date=incident_date,
            incident_location=incident_location,
            incident_type=incident_type,
            incident_severity=incident_severity,
            incident_data_json=incident_data_json,
            incident_hash=incident_hash,
        )
        await self._session_call("add", session_orm)
        await self._session.flush()
        return session_orm

    async def get_session(self, session_id: str) -> AnalysisSession | None:
        """Получить сессию по id вместе со всеми результатами."""
        stmt = (
            select(AnalysisSessionORM)
            .where(AnalysisSessionORM.id == session_id)
            .options(
                selectinload(AnalysisSessionORM.results).selectinload(RCAResultORM.causal_nodes),
                selectinload(AnalysisSessionORM.results).selectinload(RCAResultORM.recommendations),
                selectinload(AnalysisSessionORM.results).selectinload(RCAResultORM.user),
                selectinload(AnalysisSessionORM.user),
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _session_orm_to_domain(row) if row else None

    async def list_sessions(
        self,
        user_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AnalysisSession]:
        """Список сессий (без загрузки результатов — для истории)."""
        stmt = (
            select(AnalysisSessionORM)
            .options(
                selectinload(AnalysisSessionORM.user),
                selectinload(AnalysisSessionORM.results).selectinload(RCAResultORM.user),
                selectinload(AnalysisSessionORM.results).selectinload(RCAResultORM.causal_nodes),
                selectinload(AnalysisSessionORM.results).selectinload(RCAResultORM.recommendations),
            )
            .order_by(AnalysisSessionORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if user_id:
            stmt = stmt.where(AnalysisSessionORM.user_id == user_id)

        rows = (await self._session.execute(stmt)).scalars().all()
        return [_session_orm_to_domain(r) for r in rows]

    async def list_results_by_session(
        self,
        session_id: str,
        user_id: str | None = None,
    ) -> list[RCAResult]:
        """Все результаты одной сессии."""
        stmt = (
            select(RCAResultORM)
            .where(RCAResultORM.session_id == session_id)
            .options(
                selectinload(RCAResultORM.causal_nodes),
                selectinload(RCAResultORM.recommendations),
                selectinload(RCAResultORM.user),
            )
            .order_by(RCAResultORM.created_at.asc())
        )
        if user_id:
            stmt = stmt.where(RCAResultORM.user_id == user_id)

        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_domain(r) for r in rows]


# ---------------------------------------------------------------------------

from src.domain.models import MethodologyType  # noqa: E402


def _orm_to_domain(row: RCAResultORM) -> RCAResult:
    def _to_cause(n: CausalNodeORM) -> CauseNode:
        return CauseNode(
            id=n.node_id, text=n.text, category=n.category,
            level=n.level, parent_id=n.parent_id, confidence=n.confidence,
        )

    def _to_rec(r: RecommendationORM) -> Recommendation:
        return Recommendation(
            id=r.rec_id, text=r.text, priority=r.priority,
            category=r.category, cause_id=r.cause_id, responsible=r.responsible,
        )

    nodes = row.causal_nodes
    owner = row.user
    return RCAResult(
        result_id=row.result_id,
        incident_id=row.incident_id,
        session_id=row.session_id,
        user_id=row.user_id,
        user_display_name=owner.display_name if owner else None,
        user_email=owner.email if owner else None,
        methodology=MethodologyType(row.methodology),
        created_at=row.created_at,
        immediate_causes=[_to_cause(n) for n in nodes if n.node_role == "immediate"],
        contributing_causes=[_to_cause(n) for n in nodes if n.node_role == "contributing"],
        root_causes=[_to_cause(n) for n in nodes if n.node_role == "root"],
        causal_tree=[_to_cause(n) for n in nodes],
        summary=row.summary,
        recommendations=[_to_rec(r) for r in row.recommendations],
        model_used=row.model_used,
        tokens_used=row.tokens_used,
        confidence_avg=row.confidence_avg,
        draft_model_used=getattr(row, "draft_model_used", None),
        verifier_model_used=getattr(row, "verifier_model_used", None),
        draft_tokens_used=getattr(row, "draft_tokens_used", None),
        verifier_tokens_used=getattr(row, "verifier_tokens_used", None),
        verification_applied=bool(getattr(row, "verification_applied", False)),
        verification_reason=getattr(row, "verification_reason", None),
    )


def _embedding_text_from_orm(row: RCAResultORM) -> str:
    parts: list[str] = [
        f"Методология: {row.methodology}",
        row.summary,
    ]
    if row.causal_nodes:
        parts.append("Причины")
        parts.extend(node.text for node in row.causal_nodes if node.text)
    if row.recommendations:
        parts.append("Рекомендации")
        parts.extend(rec.text for rec in row.recommendations if rec.text)
    return "\n".join(part for part in parts if part).strip()


def _orm_to_similar(row: RCAResultORM, *, similarity: float) -> SimilarIncident:
    owner = row.user
    root_preview = [
        node.text for node in row.causal_nodes
        if node.node_role == "root" and node.text
    ][:3]
    rec_preview = [rec.text for rec in row.recommendations if rec.text][:3]

    # Берём описание инцидента из сессии (если есть)
    session = row.session
    incident_title = session.incident_title if session and session.incident_title != "—" else None
    incident_description = session.incident_description if session and session.incident_description != "—" else None
    incident_date = session.incident_date if session else None
    incident_location = session.incident_location if session else None

    return SimilarIncident(
        result_id=row.result_id,
        incident_id=row.incident_id,
        user_id=row.user_id,
        user_display_name=owner.display_name if owner else None,
        user_email=owner.email if owner else None,
        methodology=MethodologyType(row.methodology),
        created_at=row.created_at,
        summary=row.summary,
        similarity=max(0.0, min(1.0, similarity)),
        confidence_avg=row.confidence_avg,
        root_causes_preview=root_preview,
        recommendations_preview=rec_preview,
        incident_title=incident_title,
        incident_description=incident_description,
        incident_date=incident_date,
        incident_location=incident_location,
    )


def _session_orm_to_domain(row: AnalysisSessionORM) -> AnalysisSession:
    owner = row.user
    results = [_orm_to_domain(r) for r in row.results] if row.results else []

    # Сортируем результаты по дате (стабильный порядок)
    results.sort(key=lambda r: r.created_at)

    return AnalysisSession(
        id=row.id,
        created_at=row.created_at,
        user_id=row.user_id,
        user_display_name=owner.display_name if owner else None,
        user_email=owner.email if owner else None,
        incident_title=row.incident_title,
        incident_description=row.incident_description,
        incident_date=row.incident_date,
        incident_location=row.incident_location,
        incident_type=row.incident_type,
        incident_severity=row.incident_severity,
        incident_data_json=row.incident_data_json,
        incident_hash=row.incident_hash,
        results=results,
    )
