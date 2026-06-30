"""
Юнит-тесты для ExtractionCacheRepository.

Проверка: get() использует flush() вместо commit(), чтобы не нарушать транзакцию caller'а.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.cache_repository import ExtractionCacheRepository


@pytest.mark.asyncio
async def test_get_uses_flush_not_commit():
    """get() должен вызывать flush(), а не commit()."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    # Настроим возвращаемый результат с "строкой" (ORM-объектом)
    mock_row = MagicMock()
    mock_row.hit_count = 0
    mock_row.last_hit_at = None
    mock_row.file_hash = "test-hash"
    mock_row.extracted_fields_json = '{"title": "test"}'

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_row
    mock_session.execute.return_value = mock_result

    repo = ExtractionCacheRepository(mock_session)
    result = await repo.get("test-hash")

    assert result is not None
    # flush вызван, commit — нет
    mock_session.flush.assert_called_once()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_flush_on_cache_miss():
    """При cache miss flush не вызывается (нет данных для flush'а)."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # нет строки
    mock_session.execute.return_value = mock_result

    repo = ExtractionCacheRepository(mock_session)
    result = await repo.get("nonexistent-hash")

    assert result is None
    mock_session.flush.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_save_still_uses_commit():
    """save() и _hard_save() всё ещё используют commit() — write-операции."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = ExtractionCacheRepository(mock_session)
    await repo.save("test-hash", {"title": "test"})

    # Для save (и _hard_save) commit всё равно вызывается
    mock_session.commit.assert_called()