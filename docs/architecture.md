# architecture.md — Архитектура RCA Analyzer

> Документ описывает текущую архитектуру приложения и правила разделения ответственности между слоями.

## 1. Общая схема

```text
frontend/ React 18 + Vite
    ↓ HTTP REST / SSE
src/api/ FastAPI
    ↓ dependency injection / request models
src/services/
    ↓ orchestration
src/domain/                     src/db/
  models.py                       repository.py
  methodologies/                  models.py
    base.py                     PostgreSQL + pgvector
    five_why.py
    ishikawa.py
    fta.py
    bowtie.py
    rca_systemic.py
    ↓
src/integrations/
  llm/ OpenRouter
  embeddings/ HuggingFace/local
  export/ DOCX/PDF
```

Главная идея: HTTP-слой не содержит RCA-логики, доменный слой не знает про FastAPI, а интеграции с внешним миром изолированы в отдельных модулях.

## 2. Слои приложения

| Слой | Каталог | Ответственность |
|---|---|---|
| Frontend | `frontend/src/` | UI, формы, история, сравнение методик, SSE-прогресс, вызовы API |
| API | `src/api/` | FastAPI app, роуты, middleware, HTTP-коды, auth/CSRF на границе |
| Services | `src/services/` | Use-case orchestration: анализ, загрузка DOCX, кэш полей, вызов LLM |
| Domain | `src/domain/` | Pydantic-модели, методики RCA, разбор структурированного ответа LLM |
| DB | `src/db/` | SQLAlchemy ORM, repository, sessions/results/embeddings |
| Integrations | `src/integrations/` | OpenRouter, embeddings providers, экспорт DOCX/PDF |
| Configs | `configs/` | YAML-конфиги и Jinja2 prompts |
| Tests | `tests/` | Unit/API/contract тесты |

## 3. Backend request flow

### Одиночный анализ

```text
POST /api/v1/analyze
  → src/api/routes/analyze.py
  → AnalysisService.analyze()
  → OpenRouter LLM call
  → MethodologyRunner.run()
  → RCARepository.create_session()
  → RCARepository.save_result()
  → embedding indexing
  → RCAResult response
```

### Multi-analysis через SSE

```text
POST /api/v1/analyze-multi-stream
  → создать одну analysis_session
  → отправить SSE started
  → запустить методики параллельно через asyncio.create_task
  → на каждую методику: progress или error_one
  → done с массивом RCAResult
```

Frontend после `done` вызывает:

```text
GET /api/v1/results/compare?session_id=...
```

## 4. Analysis sessions

`analysis_sessions` — логическая единица истории.

- одиночный анализ: одна сессия + один результат;
- сравнение методик: одна сессия + несколько результатов;
- история frontend загружается через `/sessions`, чтобы пагинация шла по исследованиям, а не по отдельным RCAResult.

## 5. Similar incidents / embeddings

```text
RCAResult
  → source_text
  → EmbeddingService
  → result_embeddings.embedding
  → POST /api/v1/incidents/similar
```

Провайдеры embeddings:

- `local/hash-ngrams-v2` — deterministic fallback;
- `huggingface` — локальная HF-модель;
- `openrouter` — внешний embeddings API.

Векторы разных моделей не смешиваются: поиск фильтрует по `model_name`.

## 6. Frontend architecture

Ключевые компоненты:

| Компонент | Ответственность |
|---|---|
| `App.jsx` | Главное состояние страницы, навигация, запуск/отмена анализа |
| `IncidentForm.jsx` | Ввод инцидента, DOCX upload, выбор режима single/multi |
| `AnalysisProgress.jsx` | SSE-прогресс multi-analysis |
| `ResultView.jsx` | Отображение одного RCAResult |
| `CompareView.jsx` | Сравнение результатов одной сессии |
| `HistoryPage.jsx` | История через `/sessions` |
| `SimilarIncidentsPanel.jsx` | Поиск и открытие похожих инцидентов |
| `context/AuthContext.jsx` | Авторизация и реакция на потерю сессии |
| `components/ui/` | Button, Field, Card, Badge, Toast |

API-вызовы централизованы в `frontend/src/api.js`.

## 7. Правила расширения

### Новая RCA-методика

1. Добавить enum в `MethodologyType`.
2. Создать runner в `src/domain/methodologies/<name>.py`, наследник `MethodologyRunner`.
3. Добавить prompt `configs/prompts/<name>.j2`.
4. Зарегистрировать runner в сервисе анализа.
5. Обновить `docs/contracts.md`, `docs/methodologies.md` и тесты.

### Новый API endpoint

1. Описать контракт в `docs/contracts.md`.
2. Добавить FastAPI route.
3. Добавить тесты API.
4. Добавить метод в `frontend/src/api.js`, если endpoint нужен UI.

### Новая UI-фича

1. Переиспользовать UI-kit (`Button`, `Input`, `Select`, `Card`, `Badge`, `Toast`).
2. Не дублировать auth-логику вне `AuthContext`.
3. Ошибки пользователя показывать через `useToast()`.
4. Обновить `docs/state.md`.
