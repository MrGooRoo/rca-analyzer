# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении.

## Статус: 🟢 Рабочая версия — embeddings (E/E2), фикс 431, группировка сравнений в истории

**Дата обновления:** 2026-06-12

## Инфраструктура
- Репозиторий: `MrGooRoo/rca-analyzer`
- Docker Compose: `rca-analyzer-api-1` (FastAPI) + PostgreSQL с pgvector
  - DB image: `pgvector/pgvector:pg16`
- LLM: `nvidia/nemotron-3-super-120b-a12b:free` (1M контекст)
- Embeddings: провайдер выбирается через `EMBEDDINGS_PROVIDER`
  - `local` (default): `local/hash-ngrams-v2`, 384 dim — стемминг + словарь HSE-синонимов
  - `huggingface` (рекомендуется): локальная предобученная модель `cointegrated/rubert-tiny2`
    (29M, ~120MB, CPU), extras `pip install -e ".[embeddings]"`, model_name `hf/...`
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
- [x] **Приоритет E2 — Локальная предобученная HF-модель эмбеддингов** (11.06.2026)
  - ✅ `HFLocalEmbeddingService` (`src/integrations/embeddings/hf_local.py`)
    - default `cointegrated/rubert-tiny2` (29M, ~120MB, CPU; лучший баланс для русского по encodechka)
    - mean pooling + L2-нормализация + паддинг 312→384; E5-модели получают префикс `query:`
    - ленивая потокобезопасная загрузка, инференс в `asyncio.to_thread`, кэширование ошибки загрузки
  - ✅ `EMBEDDINGS_PROVIDER=huggingface|hf` в фабрике `get_embedding_service()`
  - ✅ Optional extras `[embeddings]` в pyproject.toml (torch CPU + transformers) — основной образ не тяжелеет
  - ✅ Автофолбэк на `local/hash-ngrams-v2`, если torch/transformers не установлены или модель недоступна
  - ✅ Качество на HSE-кейсах (similarity, hash-v2 → rubert-tiny2):
    - синонимы: 0.39–0.59 → **0.67–0.73**
    - перефраз без общих слов («травма при разгрузке фуры» ↔ «повредил руку при выгрузке грузовика»): 0.14 → **0.71**
    - несвязанные: 0.00 → 0.37–0.48 → рекомендуемый threshold для HF: **0.55–0.6**
  - ✅ Тесты: `tests/unit/test_hf_local_embeddings.py` (12 юнит + 1 интеграционный `@pytest.mark.slow`)
  - ✅ pytest: маркер `slow`, по умолчанию `-m 'not slow'` (медленные тесты не гоняются в CI)

- [x] **История: сравнение = одно исследование** (12.06.2026)
  - ✅ `HistoryPage.jsx`: результаты multi-анализа группируются по `incident_id`
    и отображаются ОДНОЙ карточкой-группой `CompareGroupCard` (а не N отдельными)
  - ✅ Карточка-группа: бейдж «⚖️ Сравнение · N методики», общий summary,
    суммарные показатели (рекомендации/токены/средняя уверенность по группе)
  - ✅ Чипы методик внутри карточки — клик открывает конкретный результат,
    клик по карточке — сравнение целиком
  - ✅ Фильтры работают по группам (методика — «хотя бы одна в группе»)
  - ⏭️ Следующий этап (вариант 2): сущность «исследование» (analysis_session) в БД
- [x] **Фикс HTTP 431 в поиске похожих** (11.06.2026)
  - ✅ Новый `POST /api/v1/incidents/similar` — текст в теле запроса (`SimilarIncidentsRequest`)
  - ✅ Причина бага: длинный текст инцидента в query string → HTTP 431 Request Header Fields Too Large
  - ✅ GET-вариант оставлен как deprecated (обратная совместимость)
  - ✅ `frontend/src/api.js`: querySimilarIncidents переведён на POST
  - ✅ +5 тестов: POST happy-path, длинный текст 5000 символов, excludes, валидация (422)

## Проверки
- `python -m pytest tests/ -q` → **235 passed, 1 deselected (slow), 8 warnings**
- `pytest -m slow -o addopts=""` (реальная rubert-tiny2) → **1 passed**
  - Остались только предсуществующие `httpx` deprecation warnings по per-request cookies в CSRF-тестах.
- `ruff check` по изменённым файлам → чисто.
- `npm run build` во frontend → **успешно** после регенерации `package-lock.json` с optional Rollup/esbuild packages.

## В работе / следующий приоритет
- [ ] **Вариант 2 — сущность «исследование» в БД** (согласовано с владельцем проекта):
  - таблица analysis_session (id, created_at, user_id, входные данные инцидента),
  - FK rca_results → analysis_session, миграция Alembic + backfill по incident_id,
  - история/сравнение читают по session_id «по конструкции», а не «по соглашению».
- [ ] Docker-интеграция HF-эмбеддингов: volume под `HF_HOME` в docker-compose,
  build-arg/target с extras `[embeddings]`, прогрев модели в lifespan FastAPI.
- [ ] Убрать оставшиеся `httpx` deprecation warnings в CSRF-тестах.
- [ ] Улучшить UX блока похожих инцидентов: открытие найденного результата из карточки, фильтры по методике/дате.
- [ ] (Опционально) Прогнать e2e с `EMBEDDINGS_PROVIDER=openrouter` на реальном ключе и сравнить качество с local v2.

## Известные проблемы / нюансы
- `EMBEDDINGS_PROVIDER=huggingface`: первый запрос скачивает модель с HF Hub (~120MB) — в Docker стоит смонтировать volume под `HF_HOME`, чтобы кэш переживал пересборку. Для нейросетевых эмбеддингов дефолтный `threshold=0.15` слишком низкий — используйте 0.55–0.6.
- Смешивать провайдеры безопасно: поиск фильтрует по `model_name`, backfill лениво переиндексирует чужие векторы.
- При `EMBEDDINGS_PROVIDER=openrouter` embeddings становятся платными запросами (text-embedding-3-small ≈ $0.02/1M токенов); при недоступности API всё автоматически работает через local v2.
- После смены провайдера старые векторы переиндексируются лениво (батчами по 100 при каждом поиске похожих); до полной переиндексации часть старых результатов не попадает в выдачу.
- Для production БД требуется `pgvector`: Docker Compose уже переведён на `pgvector/pgvector:pg16`, миграция создаёт `CREATE EXTENSION IF NOT EXISTS vector`.
- На существующей БД после обновления нужно выполнить `alembic upgrade head`.
