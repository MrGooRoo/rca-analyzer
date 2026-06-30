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

        # Обновляем статистику попаданий. flush(), а не commit(): get() —
        # read-операция, а commit() закрыл бы транзакцию caller'а (напр. в
        # upload.py), и последующий rollback уже не откатил бы hit_count.
        row.hit_count += 1
        row.last_hit_at = datetime.now(UTC)
        await self._session.flush()

        logger.info(
            "[ExtractionCache] Попадание в кэш: hash=%s hit_count=%d",
            file_hash[:16], row.hit_count,
        )
        return json.loads(row.extracted_fields_json)

    async def save(self, file_hash: str, fields: dict) -> None:
        """Сохранить результат извлечения в кэш (без incident_hash — обратная совместимость)."""
        await self._hard_save(file_hash, None, fields)

    async def _hard_save(self, file_hash: str, incident_hash: str | None, fields: dict) -> None:
        """Сохранить результат с указанием incident_hash.
        
        Если запись с таким file_hash уже есть — пропускаем.
        """
        stmt = select(DocxExtractionCacheORM).where(
            DocxExtractionCacheORM.file_hash == file_hash
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            logger.debug("[ExtractionCache] Запись уже есть, пропуск сохранения: hash=%s", file_hash[:16])
            return

        row = DocxExtractionCacheORM(
            file_hash=file_hash,
            incident_hash=incident_hash,
            extracted_fields_json=json.dumps(fields, ensure_ascii=False),
        )
        self._session.add(row)
        await self._session.commit()
        logger.info("[ExtractionCache] Сохранено в кэш: hash=%s", file_hash[:16])

    async def delete(self, file_hash: str) -> bool:
        """Удалить запись из кэша по хешу файла. Вернуть True если была удалена."""
        stmt = select(DocxExtractionCacheORM).where(
            DocxExtractionCacheORM.file_hash == file_hash
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        logger.info("[ExtractionCache] Удалено: hash=%s", file_hash[:16])
        return True

    async def find_by_incident_hash(self, incident_hash: str) -> dict | None:
        """Найти кэш по incident_hash (SHA-256 title+description)."""
        stmt = select(DocxExtractionCacheORM).where(
            DocxExtractionCacheORM.incident_hash == incident_hash
        ).order_by(DocxExtractionCacheORM.created_at.desc()).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        logger.info(
            "[ExtractionCache] Найден по incident_hash=%s — hash файла %s",
            incident_hash[:16], row.file_hash[:16],
        )
        return json.loads(row.extracted_fields_json)

    async def list_all(self) -> list[dict]:
        """Вернуть список всех записей кэша."""
        from sqlalchemy import desc
        stmt = select(DocxExtractionCacheORM).order_by(desc(DocxExtractionCacheORM.created_at)).limit(200)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            {
                "file_hash": r.file_hash,
                "incident_hash": r.incident_hash,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "hit_count": r.hit_count,
                "extracted_fields_json": r.extracted_fields_json,
            }
            for r in rows
        ]

    async def get_by_hash(self, file_hash: str) -> dict | None:
        """Вернуть одну запись с полными данными."""
        stmt = select(DocxExtractionCacheORM).where(
            DocxExtractionCacheORM.file_hash == file_hash
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return {
            "file_hash": row.file_hash,
            "incident_hash": row.incident_hash,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "hit_count": row.hit_count,
            "extracted_fields_json": row.extracted_fields_json,
        }
