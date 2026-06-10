"""
Сервис кэширования LLM-извлечения DOCX-полей.

Оборачивает extract_fields_from_text() проверкой кэша по SHA-256 хешу файла.

Логика:
  1. Вычислить SHA-256 от байт файла.
  2. Поискать в таблице docx_extraction_cache.
  3. Попадание  → вернуть кэшированные поля немедленно (экономия ~6 мин).
  4. Промах     → вызвать extract_fields_from_text(), сохранить в кэш, вернуть.

Использование:
    from src.services.docx_cache_service import get_or_extract

    fields = await get_or_extract(file_bytes, db_session)
"""

from __future__ import annotations

import hashlib
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.cache_repository import ExtractionCacheRepository
from src.services.docx_fields_service import extract_fields_from_text

logger = logging.getLogger(__name__)


def _sha256(data: bytes) -> str:
    """Вычислить SHA-256 хеш файла в hex-формате."""
    return hashlib.sha256(data).hexdigest()


async def get_or_extract(file_bytes: bytes, session: AsyncSession) -> dict:
    """
    Вернуть поля инцидента из кэша или вызвать LLM-извлечение.

    Args:
        file_bytes: Байты DOCX-файла.
        session:    Асинхронная сессия SQLAlchemy.

    Returns:
        Словарь извлечённых полей (тот же формат, что возвращает
        extract_fields_from_text).
    """
    file_hash = _sha256(file_bytes)
    repo = ExtractionCacheRepository(session)

    cached = await repo.get(file_hash)
    if cached is not None:
        logger.info(
            "[DocxCache] Кэш-попадание: hash=%s... — LLM-извлечение пропущено",
            file_hash[:16],
        )
        return cached

    logger.info(
        "[DocxCache] Кэш-промах: hash=%s... — запускаю LLM-извлечение",
        file_hash[:16],
    )
    fields = await extract_fields_from_text_from_bytes(file_bytes)
    await repo.save(file_hash, fields)
    return fields


async def extract_fields_from_text_from_bytes(file_bytes: bytes) -> dict:
    """
    Извлечь текст из байт DOCX и прогнать через LLM.
    Вынесено отдельно, чтобы не импортировать docx_extractor в cache_service
    с циклической зависимостью.
    """
    from src.services.docx_extractor import extract_text_from_docx
    report_text = extract_text_from_docx(file_bytes)
    return await extract_fields_from_text(report_text)
