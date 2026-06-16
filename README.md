# RCA Analyzer

Веб-приложение для анализа корневых причин (RCA) производственных инцидентов.

Проект помогает собрать данные об инциденте, запустить анализ по одной или нескольким
RCA-методикам, сравнить выводы, сохранить историю, найти похожие прошлые случаи и
экспортировать результат в DOCX/PDF.

---

## Возможности

- **5 RCA-методик:** `five_why`, `ishikawa`, `fta`, `rca_systemic`, `bowtie`.
- **Одиночный анализ** по выбранной методике.
- **Сравнение методик** по одному инциденту: несколько результатов группируются как одно исследование.
- **История анализов** с группировкой сравнений, фильтрами и просмотром результатов.
- **Похожие инциденты** через embeddings + pgvector:
  - локальный deterministic provider `local/hash-ngrams-v2`;
  - HuggingFace local model `cointegrated/rubert-tiny2`;
  - OpenRouter embeddings provider.
- **Дедуп похожих случаев** через `incident_hash` от заголовка и описания инцидента.
- **DOCX upload**: загрузка отчёта и автозаполнение формы через LLM.
- **Экспорт DOCX/PDF** из результата анализа.
- **Авторизация:** cookie-based auth, refresh-token rotation, CSRF, роли `admin/user`.
- **UI-kit:** Button, Field/Input/Textarea/Select, Card/Badge, Toast, AuthContext.

---

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python, FastAPI, Pydantic v2 |
| База данных | PostgreSQL 16 + pgvector, SQLAlchemy, Alembic |
| LLM | OpenRouter, default `nvidia/nemotron-3-super-120b-a12b:free` |
| Embeddings | local / HuggingFace / OpenRouter |
| Frontend | React 18 + Vite |
| UI | CSS + UI-kit компоненты проекта, Tailwind utilities |
| Auth | JWT access + refresh-token в httpOnly cookie, CSRF |
| Export | python-docx, fpdf2 |
| Контейнеризация | Docker Compose |

---

## Быстрый старт

### 1. Подготовить `.env`

Создайте `.env` в корне проекта на основе `.env.example` и укажите минимум:

```env
OPENROUTER_API_KEY=...
JWT_SECRET=change-me-long-random-secret
DATABASE_URL=postgresql+asyncpg://rca:secret@db:5432/rca_analyzer
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
```

### 2. Запустить backend + PostgreSQL

```bash
docker compose up -d --build
```

### 3. Применить миграции

```bash
docker compose exec api alembic upgrade head
```

### 4. Запустить frontend dev-server

В отдельном терминале:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

### 5. Открыть приложение

| Что | Адрес |
|---|---|
| Frontend | http://localhost:5173/ |
| API / Swagger | http://localhost:8000/docs |
| Healthcheck | http://localhost:8000/health |

> `http://localhost:8000/` может вернуть `{"detail":"Not Found"}` — это нормально:
> корень FastAPI не является страницей приложения. Для API используйте `/docs`,
> для интерфейса — порт `5173`.

---

## Docker Compose

`docker-compose.yml` поднимает:

- `db` — `pgvector/pgvector:pg16`;
- `api` — FastAPI на `http://localhost:8000`.

Frontend в текущей dev-схеме запускается отдельно через Vite (`npm run dev`).

Полезные команды:

```bash
# пересобрать backend и БД-сервис
docker compose down
docker compose up -d --build

# логи API
docker compose logs -f api

# миграции
docker compose exec api alembic upgrade head
```

---

## Основные сценарии

### Одиночный анализ

1. Открыть `http://localhost:5173/`.
2. Войти или зарегистрироваться.
3. Заполнить форму инцидента или загрузить DOCX.
4. Выбрать режим «Одна методика».
5. Запустить анализ.
6. После результата форма скрывается, появляется панель результата и кнопка «Новый анализ».

### Сравнение методик

1. В форме выбрать режим «Сравнить методики».
2. Выбрать минимум 2 методики.
3. Запустить сравнение.
4. Результаты сохраняются в одну `analysis_session` и отображаются в истории как одно исследование.

### Похожие инциденты

- В форме отображается лёгкий индикатор похожих случаев.
- В результате анализа показывается полный блок похожих инцидентов.
- Повторные анализы того же инцидента исключаются через `incident_hash`.

---

## API endpoints

### Auth

| Метод | Endpoint | Описание |
|---|---|---|
| GET | `/api/v1/auth/csrf` | Получить CSRF cookie для login/register |
| POST | `/api/v1/auth/register` | Регистрация |
| POST | `/api/v1/auth/login` | Вход |
| POST | `/api/v1/auth/refresh` | Refresh-token rotation |
| POST | `/api/v1/auth/logout` | Выход |
| GET | `/api/v1/auth/me` | Текущий пользователь |

### Анализ и история

| Метод | Endpoint | Описание |
|---|---|---|
| POST | `/api/v1/analyze` | Одиночный RCA-анализ |
| POST | `/api/v1/analyze-multi` | Анализ несколькими методиками |
| POST | `/api/v1/analyze-multi-stream` | Streaming multi-analysis events |
| GET | `/api/v1/results` | История результатов |
| GET | `/api/v1/results/{result_id}` | Полный результат |
| GET | `/api/v1/results/compare?session_id=...` | Сравнение результатов сессии |
| GET | `/api/v1/sessions` | Список исследований |
| GET | `/api/v1/sessions/{session_id}` | Исследование по ID |

### Upload / export / similar

| Метод | Endpoint | Описание |
|---|---|---|
| POST | `/api/v1/upload-report` | Загрузить DOCX и извлечь поля |
| POST | `/api/v1/upload-report-stream` | Streaming upload progress |
| GET | `/api/v1/results/{result_id}/export?format=docx|pdf` | Экспорт результата |
| POST | `/api/v1/incidents/similar` | Поиск похожих инцидентов |

### Admin

| Метод | Endpoint | Описание |
|---|---|---|
| GET | `/api/v1/admin/users` | Список пользователей, admin only |
| PUT | `/api/v1/admin/users/{user_id}/role` | Изменить роль пользователя |

---

## Embeddings

Выбор провайдера через `.env`:

```env
EMBEDDINGS_PROVIDER=local        # local | huggingface | openrouter
```

| Provider | Модель / поведение | Рекомендуемый threshold |
|---|---|---|
| `local` | `local/hash-ngrams-v2`, deterministic feature hashing, 384 dim | `0.15` |
| `huggingface` | `cointegrated/rubert-tiny2`, CPU, кэш в `HF_HOME` | `0.55–0.6` |
| `openrouter` | OpenAI-compatible embeddings endpoint через OpenRouter | `0.55–0.6` |

Векторы разных моделей не смешиваются: поиск фильтрует по `model_name`.
При ошибке внешнего провайдера выполняется fallback на `local/hash-ngrams-v2`.

---

## Проверки для разработки

```bash
# backend tests
python -m pytest tests/ -q

# lint
ruff check

# frontend build
npm --prefix frontend run build
```

Текущий ожидаемый результат:

```text
257 passed, 1 deselected
ruff: All checks passed
frontend: build successful
```

---

## Структура проекта

```text
rca-analyzer/
├── src/
│   ├── api/                    # FastAPI app, middleware, routes
│   ├── auth/                   # auth, cookies, CSRF, roles
│   ├── db/                     # ORM models, repository
│   ├── domain/                 # Pydantic models, RCA methodologies
│   ├── integrations/           # OpenRouter, embeddings integrations
│   └── services/               # analysis, DOCX/PDF export, upload parsing, embeddings
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       ├── components/
│       ├── components/ui/      # Button, Card, Field, Toast
│       ├── context/            # AuthContext
│       └── lib/                # methodologies metadata
├── alembic/versions/           # DB migrations
├── configs/prompts/            # Jinja2 prompts for RCA methodologies
├── docs/
│   ├── contracts.md            # data/API contracts
│   ├── state.md                # current implementation status
│   └── ui-state-analysis.md    # UI state decisions/issues
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## Документация статуса

Актуальный технический статус проекта ведётся в:

- [`docs/state.md`](docs/state.md)
- [`docs/contracts.md`](docs/contracts.md)
- [`docs/ui-state-analysis.md`](docs/ui-state-analysis.md)

README — краткая точка входа. Детальные контракты и принятые решения находятся в `docs/`.

---

## Production hardening checklist

- [ ] Задать длинный случайный `JWT_SECRET`.
- [ ] Включить `AUTH_COOKIE_SECURE=true` под HTTPS.
- [ ] Настроить `AUTH_COOKIE_SAMESITE` под схему доменов.
- [ ] Ограничить `CORS_ALLOW_ORIGINS` конкретными доменами.
- [ ] Задать отдельный `CSRF_SECRET` или использовать надёжный `JWT_SECRET`.
- [ ] Выполнить `alembic upgrade head` на production DB.
- [ ] Для HuggingFace embeddings подключить persistent volume для `HF_HOME`.

---

## Лицензия

Проект разрабатывается в репозитории `MrGooRoo/rca-analyzer`.


