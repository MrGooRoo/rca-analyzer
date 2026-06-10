# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении.

## Статус: 🟢 Рабочая версия — приоритет D завершён (baseline RAG)

**Дата обновления:** 2026-06-10

## Инфраструктура
- Репозиторий: `MrGooRoo/rca-analyzer`
- Docker Compose: `rca-analyzer-api-1` (FastAPI) + PostgreSQL с pgvector
  - DB image: `pgvector/pgvector:pg16`
- LLM: `nvidia/nemotron-3-super-120b-a12b:free` (1M контекст)
- Embeddings: `local/hash-ngrams-v1`, размерность 384 (детерминированный локальный baseline без внешних API)

## Готово
- [x] Все 5 методологий
- [x] Авторизация, CSRF, роли admin/user
- [x] Анализ, результаты, экспорт DOCX/PDF, upload DOCX
- [x] **Сравнение методик — бэкенд** (08.06.2026)
  - POST /api/v1/analyze-multi
  - GET /api/v1/results/compare?incident_id=...
  - Модели MultiAnalysisRequest + ComparisonResult
- [x] **Сравнение методик — UI** (08.06.2026, приоритет B)
  - Режим «Одна методика» / «Сравнить методики» в IncidentForm
  - CompareView: сводка, общие рекомендации, различающиеся выводы, side-by-side табы
- [x] **Приоритет C — Почистить/улучшить бэкенд** (08.06.2026)
  - ✅ Валидация MultiAnalysisRequest: мин 2, макс 5 уникальных методик (422 при нарушении)
  - ✅ Обработка ошибок в /analyze-multi (400, 502, 500) и /results/compare (404, 500)
  - ✅ Улучшен compare() — нечёткое сравнение через SequenceMatcher (порог 0.55)
  - ✅ Общие рекомендации (в ≥2 методиках), уникальные причины, информативная сводка
  - ✅ Фикс маршрутизации: /results/compare ДО /results/{result_id}
  - ✅ 24 новых теста (валидация, compare-логика, роуты /analyze-multi, /results/compare)
  - ✅ conftest.py с env vars для тестов
  - ✅ Обновлены contracts.md и state.md
- [x] **Приоритет D — Векторный поиск похожих инцидентов / RAG baseline** (10.06.2026)
  - ✅ Локальный embedding-сервис `LocalHashEmbeddingService` (`local/hash-ngrams-v1`, 384 dim)
  - ✅ PostgreSQL vector storage через `pgvector` и таблицу `result_embeddings`
  - ✅ Alembic migration `007_add_result_embeddings.py`
  - ✅ Автоматическая индексация каждого нового `RCAResult` при `repo.save_result()`
  - ✅ Backfill старых результатов при поиске похожих (`backfill_missing_embeddings`)
  - ✅ API: `GET /api/v1/incidents/similar?text=...&limit=5&threshold=0.15`
  - ✅ Ограничение доступа: user видит только свои похожие инциденты, admin — все
  - ✅ Frontend API: `api.similarIncidents(text, options)`
  - ✅ UI-компонент `SimilarIncidentsPanel`
    - в `IncidentForm` — ручной поиск похожих до запуска анализа
    - в `ResultView` — автоматический блок похожих после анализа
  - ✅ Тесты: `tests/unit/test_embedding_service.py`, `tests/api/test_similar_incidents.py`

## Проверки
- `python -m pytest tests/ -q` → **193 passed, 8 warnings**
  - Остались только предсуществующие `httpx` deprecation warnings по per-request cookies в CSRF-тестах.
- `npm run build` во frontend → **успешно** после регенерации `package-lock.json` с optional Rollup/esbuild packages.

## В работе / следующий приоритет
- [ ] Улучшить качество embeddings:
  - заменить/дополнить `local/hash-ngrams-v1` внешней embedding-моделью (OpenRouter или отдельный embedding API),
  - либо добавить более умную локальную нормализацию/синонимы для русскоязычных HSE-инцидентов.
- [ ] Убрать оставшиеся `httpx` deprecation warnings в CSRF-тестах.
- [ ] Улучшить UX блока похожих инцидентов: открытие найденного результата из карточки, фильтры по методике/дате.

## Известные проблемы / нюансы
- Поиск похожих реализован как deterministic baseline: хорошо ловит лексически похожие случаи, но хуже понимает синонимы без общих слов.
- Для production БД требуется `pgvector`: Docker Compose уже переведён на `pgvector/pgvector:pg16`, миграция создаёт `CREATE EXTENSION IF NOT EXISTS vector`.
- На существующей БД после обновления нужно выполнить `alembic upgrade head`.
