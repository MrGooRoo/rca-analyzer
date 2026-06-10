# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении.

## Статус: 🟢 Рабочая версия — приоритет E завершён (качество embeddings)

**Дата обновления:** 2026-06-11

## Инфраструктура
- Репозиторий: `MrGooRoo/rca-analyzer`
- Docker Compose: `rca-analyzer-api-1` (FastAPI) + PostgreSQL с pgvector
  - DB image: `pgvector/pgvector:pg16`
- LLM: `nvidia/nemotron-3-super-120b-a12b:free` (1M контекст)
- Embeddings: провайдер выбирается через `EMBEDDINGS_PROVIDER`
  - `local` (default): `local/hash-ngrams-v2`, 384 dim — стемминг + словарь HSE-синонимов
  - `openrouter`: `openai/text-embedding-3-small` (или любая из OPENROUTER_EMBEDDING_MODEL), приводится к 384 dim

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
- [x] **Приоритет E — Качество embeddings** (11.06.2026)
  - ✅ Локальная модель v2: `local/hash-ngrams-v2`
    - лёгкий русский стемминг (снятие окончаний, признак `stem:`)
    - словарь HSE-концептов `_CONCEPT_PREFIXES` (~17 концептов: fall, ladder, fire,
      electricity, gas, chemical, ppe, training, …) — признак `concept:` с весом 1.6
    - синонимы без общих слов теперь сближаются: «упал со стремянки» ↔ «падение с лестницы»
      similarity 0.04 (v1) → **0.46 (v2)**; «удар током» ↔ «поражение электротоком» 0.11 → **0.59**
  - ✅ Внешний провайдер: `OpenRouterEmbeddingService` (`src/integrations/llm/openrouter_embeddings.py`)
    - POST /api/v1/embeddings (OpenAI-совместимый), default `openai/text-embedding-3-small`
    - dimensions=384 (Matryoshka) c фолбэком на усечение/паддинг + L2-нормализация
    - retry/backoff на 408/429/5xx, обработка моделей без поддержки `dimensions`
  - ✅ Фабрика `get_embedding_service()` по env `EMBEDDINGS_PROVIDER` (local | openrouter)
  - ✅ `RCARepository._embed()`: поддержка sync/async-провайдеров + автофолбэк на local при `EmbeddingServiceError`
  - ✅ Поиск похожих фильтрует по `model_name` — векторы разных моделей не смешиваются
  - ✅ `backfill_missing_embeddings` переиндексирует записи другой модели (ленивая миграция при смене провайдера)
  - ✅ `.env.example`: блок Embeddings (EMBEDDINGS_PROVIDER, OPENROUTER_EMBEDDING_*)
  - ✅ Тесты: `tests/unit/test_embedding_quality.py` (11), `tests/unit/test_openrouter_embeddings.py` (11, respx)

## Проверки
- `python -m pytest tests/ -q` → **215 passed, 8 warnings**
  - Остались только предсуществующие `httpx` deprecation warnings по per-request cookies в CSRF-тестах.
- `ruff check` по изменённым файлам → чисто.
- `npm run build` во frontend → **успешно** после регенерации `package-lock.json` с optional Rollup/esbuild packages.

## В работе / следующий приоритет
- [ ] Убрать оставшиеся `httpx` deprecation warnings в CSRF-тестах.
- [ ] Улучшить UX блока похожих инцидентов: открытие найденного результата из карточки, фильтры по методике/дате.
- [ ] (Опционально) Прогнать e2e с `EMBEDDINGS_PROVIDER=openrouter` на реальном ключе и сравнить качество с local v2.

## Известные проблемы / нюансы
- При `EMBEDDINGS_PROVIDER=openrouter` embeddings становятся платными запросами (text-embedding-3-small ≈ $0.02/1M токенов); при недоступности API всё автоматически работает через local v2.
- После смены провайдера старые векторы переиндексируются лениво (батчами по 100 при каждом поиске похожих); до полной переиндексации часть старых результатов не попадает в выдачу.
- Для production БД требуется `pgvector`: Docker Compose уже переведён на `pgvector/pgvector:pg16`, миграция создаёт `CREATE EXTENSION IF NOT EXISTS vector`.
- На существующей БД после обновления нужно выполнить `alembic upgrade head`.
