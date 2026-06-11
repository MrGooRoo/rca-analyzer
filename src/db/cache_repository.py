"""
Репозиторий кэша LLM-извлечения DOCX.

Хранит и извлекает результаты extract_fields_from_text() по SHA-256 хешу файла.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.orm_models import DocxExtractionCacheORM

logger = logging.getLogger(__name__)


class ExtractionCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, file_hash: str) -> dict | None:
        """
        Вернуть кэшированные поля для данного хеша файла.
        Обновляет hit_count и last_hit_at при попадании.
        Возвращает None при промахе.
        """
        stmt = select(DocxExtractionCacheORM).where(
            DocxExtractionCacheORM.file_hash == file_hash
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None

        # Обновляем статистику попаданий
        row.hit_count += 1
        row.last_hit_at = datetime.now(UTC)
        await self._session.commit()

        logger.info(
            "[ExtractionCache] Попадание в кэш: hash=%s hit_count=%d",
            file_hash[:16], row.hit_count,
        )
        return json.loads(row.extracted_fields_json)

    async def save(self, file_hash: str, fields: dict) -> None:
        """
        Сохранить результат извлечения в кэш.
        Если запись с таким хешем уже есть — пропускаем (race condition).
        """
        existing = await self.get.__wrapped__(self, file_hash) if hasattr(self.get, "__wrapped__") else None
        # Простая проверка без рекурсии
        stmt = select(DocxExtractionCacheORM).where(
            DocxExtractionCacheORM.file_hash == file_hash
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            logger.debug("[ExtractionCache] Запись уже есть, пропуск сохранения: hash=%s", file_hash[:16])
            return

        row = DocxExtractionCacheORM(
            file_hash=file_hash,
            extracted_fields_json=json.dumps(fields, ensure_ascii=False),
        )
        self._session.add(row)
        await self._session.commit()
        logger.info("[ExtractionCache] Сохранено в кэш: hash=%s", file_hash[:16])
