# RCA Analyzer

Веб-приложение для анализа корневых причин (RCA) производственных инцидентов.
Поддерживает 5 методологий, cookie-авторизацию с refresh-rotation, изолированную историю результатов по пользователям, загрузку DOCX-отчёта для автозаполнения формы и экспорт результатов.

---

## Стек

| Слой | Технология |
|---|---|
| Backend | FastAPI (Python 3.11) |
| База данных | PostgreSQL + SQLAlchemy + Alembic |
| LLM | OpenRouter → `openai/gpt-4o-mini` (fallback: `gpt-oss-120b:free`) |
| Frontend | React (Vite) |
| Контейнеризация | Docker Compose |
| Авторизация | JWT access + refresh-token в httpOnly cookie, bcrypt |
| Экспорт | python-docx → DOCX-файл |

---

## Быстрый старт

```bash
cd C:\Users\Mr_GooRoo\rca-analyzer
git pull origin main
docker-compose down && docker-compose up -d --build
docker-compose exec api alembic upgrade head
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
Frontend: [http://localhost:5173](http://localhost:5173)

---

## Методологии

| Методология | Статус | ~Токены |
|---|---|---|
| `five_why` | ✅ работает | ~951 |
| `ishikawa` | ✅ работает | ~2267 |
| `rca_systemic` | ✅ работает | ~1504 |
| `fta` | ✅ работает | ~1446 |
| `bowtie` | ✅ работает | ~3138 |

Все 5 методологий прошли полный smoke-test (UI → анализ → скачивание DOCX) 05.06.2026.

---

## API

### Авторизация

| Метод | Эндпойнт | Описание |
|---|---|---|
| POST | `/api/v1/auth/register` | Регистрация → устанавливает access/refresh cookie |
| POST | `/api/v1/auth/login` | Вход → устанавливает access/refresh cookie |
| POST | `/api/v1/auth/refresh` | Обновить сессию по refresh cookie (rotation) |
| POST | `/api/v1/auth/logout` | Отозвать текущий refresh-токен и очистить cookie |
| GET | `/api/v1/auth/me` | Профиль текущего пользователя |

### CSRF-защита (cookie-based auth)

Поскольку access/refresh-токены живут в `httpOnly` cookie, которые браузер
отправляет автоматически, приложение защищено от CSRF по схеме
**signed double-submit cookie** (defense-in-depth поверх `SameSite`).

**Как это работает:**

1. На `register` / `login` / `refresh` сервер ставит **не-httpOnly** cookie
   `csrf_token` со значением `<random>.<hmac_sha256(random, secret)>`.
2. Frontend читает значение из `document.cookie` и отправляет его в заголовке
   `X-CSRF-Token` при каждом **небезопасном** запросе (POST/PUT/PATCH/DELETE).
3. `CSRFMiddleware` проверяет, что cookie присутствует, подпись валидна, а
   значения cookie и заголовка совпадают. Иначе — `403`.

**Что освобождено от проверки (не сломает интеграции):**

| Случай | Почему exempt |
|---|---|
| GET / HEAD / OPTIONS | safe-методы, не меняют состояние |
| `login` / `register` / `refresh` | bootstrap: у клиента ещё нет csrf-cookie |
| `Authorization: Bearer ...` без access-cookie | не подвержен ССРФ → Swagger «Аутхоризе» и `curl` работают как раньше |
| анонимные запросы (нет access-cookie) | нечего защищать |

**Поведение управляется** переменными `CSRF_PROTECTION_ENABLED`,
`CSRF_EXEMPT_PATHS`, `CSRF_SECRET` (см. раздел «Переменные окружения»).
Серверного хранилища CSRF-токенов нет — stateless, без новой таблицы/миграции.

### Анализ (требует auth-cookie или Bearer-токен)

| Метод | Эндпойнт | Описание |
|---|---|---|
| POST | `/api/v1/analyze` | Запуск RCA-анализа |
| GET | `/api/v1/results` | История результатов текущего пользователя |
| GET | `/api/v1/results/{id}` | Результат по ID |
| GET | `/api/v1/results/{id}/export` | Скачать DOCX-отчёт |
| POST | `/api/v1/upload-report` | Загрузить DOCX → автозаполнить форму через LLM |

---

## Загрузка DOCX-отчёта

Эндпойнт: `POST /api/v1/upload-report` (multipart/form-data, файл `file`)

**Что происходит:**
1. `DocxExtractor` извлекает текст из DOCX (абзацы + таблицы)
2. Текст обрезается стратегией **head + tail + section-aware** (см. ниже)
3. LLM извлекает до 20 полей (заголовок, описание, дата, место, установленные факты, пострадавшие и др.)
4. Форма в UI заполняется извлечёнными данными

**Стратегия обрезки текста (`docx_fields_service._trim_text`):**
- Документы ≤ `HEAD_CHUNK + TAIL_CHUNK` (16 000 сим.) передаются целиком.
- Для длинных документов берём:
  - **head** — первые `8 000` сим. (обзор, даты, пострадавшие);
  - **tail** — последние `8 000` сим. (часто заключение);
  - **section slices** — целевые срезы (`SECTION_WINDOW = 6 000`) вокруг ключевых
    разделов (`Установленные факты`, `Обстоятельства`, `Причины` и др.),
    найденных **в любом месте** документа.
- Это решает проблему пустого `established_facts`: раздел гарантированно попадает
  в срез, даже если он в «мёртвой зоне» между head и tail (тестовый документ
  `165 066` сим. — раздел на позиции ~48 895, успешно захватывается).
- Между сохранёнными фрагментами вставляется метка `...[пропущено N символов]...`.

**LLM клиент (upload):**
- `required_keys={"title"}` — не проверяет `summary`/`recommendations` (они нужны только RCA-методологиям)
- `max_tokens=4096` — достаточно для крупных JSON с `victims_list`

**Проверка / тесты:**
- `pytest tests/unit/test_docx_fields_service.py` — 13 тестов на `_trim_text`
- `python scripts/verify_established_facts.py [path.docx]` — e2e-проверка без LLM

---

## Экспорт DOCX

Эндпойнт: `GET /api/v1/results/{result_id}/export` (требует auth-cookie или Bearer-токен)

DOCX-файл содержит:

1. Заголовок — методология, ID, дата, модель, токены, уверенность
2. Резюме
3. Причины (для bowtie: Hazard, Топ-событие, Угрозы, Барьеры предотвращения, Последствия, Барьеры смягчения; деградированные барьеры помечены ⚠)
4. Рекомендации — таблица с приоритетом, категорией, ответственным
5. Техническая информация

Имя файла: `rca_{methodology}_{result_id[:8]}.docx`

В UI: кнопка **⬇️ DOCX** в шапке каждого результата (`ResultView.jsx`).

---

## Структура проекта

```
rca-analyzer/
├── src/
│   ├── auth/                   # Access JWT, refresh-token rotation, cookies, bcrypt
│   ├── api/
│   │   ├── app.py              # CORS + credentials, роутеры (v0.5.0)
│   │   └── routes/
│   │       ├── analyze.py      # Защищён cookie/Bearer auth, пишет user_id
│   │       ├── export.py       # GET /results/{id}/export → DOCX
│   │       └── upload.py       # POST /upload-report → извлечение полей через LLM
│   ├── db/
│   │   ├── orm_models.py       # UserORM, RefreshTokenORM, IncidentORM, RCAResultORM
│   │   └── repository.py       # CRUD
│   ├── domain/
│   │   ├── models.py           # RCAResult, CauseNode, Recommendation
│   │   └── methodologies/      # five_why, ishikawa, rca_systemic, fta, bowtie
│   ├── integrations/llm/
│   │   └── openrouter.py       # AsyncClient; required_keys param; retry x3
│   └── services/
│       ├── analysis_service.py # Оркестратор, реестр _RUNNERS (все 5)
│       ├── export_service.py   # Генерация DOCX (все 5 методологий)
│       ├── docx_extractor.py   # Извлечение текста из DOCX
│       └── docx_fields_service.py  # LLM-парсинг полей из текста отчёта
├── frontend/
│   └── src/
│       ├── api.js              # Централизованный fetch; exportDocx() скачивает blob; uploadReport()
│       ├── App.jsx             # Login-gate, навигация, logout, обработка 401
│       └── components/
│           ├── AuthPage.jsx        # вход / регистрация
│           ├── HistoryPage.jsx     # история через api.js
│           ├── IncidentForm.jsx    # форма, drag-and-drop загрузка .docx
│           ├── ResultView.jsx      # кнопка ⬇️ DOCX, без прямых HTTP-запросов
│           ├── BowtieDiagram.jsx   # диаграмма (v6), интегрирована в ResultView
│           └── BowtieDiagram.css
├── configs/prompts/            # Jinja2-шаблоны: five_why, ishikawa, fta, rca_systemic, bowtie
├── alembic/versions/
│   ├── 001_initial.py
│   ├── 002_fix_varchar_lengths.py
│   ├── 003_add_users.py        # users + user_id в incidents/rca_results
│   └── 004_add_refresh_tokens.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml              # v0.5.0
└── .env                        # Создаётся вручную (не в git)
```

---

## Переменные окружения (`.env`)

```env
DATABASE_URL=postgresql+asyncpg://...
OPENROUTER_API_KEY=...
JWT_SECRET=...                # секрет для HS256
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=30
AUTH_COOKIE_SECURE=false       # prod: true (cookie только по HTTPS)
AUTH_COOKIE_SAMESITE=lax       # cross-domain prod: none (+ AUTH_COOKIE_SECURE=true)
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000

# CSRF (signed double-submit cookie)
CSRF_PROTECTION_ENABLED=true   # выключатель защиты (dev можно false)
# CSRF_SECRET=                 # секрет подписи; если пусто — используется JWT_SECRET
# CSRF_EXEMPT_PATHS=           # доп. exempt-пути через запятую (точное совпадение)
# CSRF_COOKIE_NAME=csrf_token
# CSRF_HEADER_NAME=X-CSRF-Token
```

---

## Миграции

```bash
docker-compose exec api alembic upgrade head      # применить все
 docker-compose exec api alembic revision --autogenerate -m "name"  # новая
```

---

## Ключевые архитектурные решения

- **bcrypt напрямую** (без passlib) — обход бага совместимости с `bcrypt ≥ 4.x`
- **Access/refresh в httpOnly cookie** — frontend не хранит токены ни в памяти, ни в `localStorage`
- **Refresh-token rotation** — при `POST /api/v1/auth/refresh` старый refresh-токен помечается revoked, клиент получает новую пару cookie
- **user_id** сохраняется в `incidents` и `rca_results`; `GET /api/v1/results` возвращает только записи текущего пользователя
- **OpenRouterClient** создаётся на каждый запрос (`async with`) — предотвращает повторное использование закрытого `httpx.AsyncClient`
- **`required_keys` param** в `OpenRouterClient.complete()` — upload передаёт `{"title"}`, RCA-раннеры ничего не меняют (дефолт `{"summary", "recommendations"}`)
- **Frontend HTTP** — вся сетевая логика централизована в `api.js`; `401` вызывает авто-refresh и один retry
- **BowtieDiagram** интегрирован в `ResultView` — автоматически отображается для `methodology === 'bowtie'`
- **CSRF: signed double-submit cookie** — stateless, без таблицы; Bearer/Swagger/curl освобождены
- **Export DOCX** — `export_service.py` через `python-docx`; отдельные секции для каждой методологии

---

## Production hardening (чеклист перед деплоем)

- [ ] **`JWT_SECRET`** — задать длинный случайный секрет (`openssl rand -hex 32`)
- [ ] **`AUTH_COOKIE_SECURE=true`** — cookie только по HTTPS
- [ ] **`CSRF_PROTECTION_ENABLED=true`** — оставить включённым
- [ ] **`SameSite`**: один домен → `lax`; разные домены → `none` + `SECURE=true`
- [ ] **`CORS_ALLOW_ORIGINS`** — только реальные домены (no `*`)

---

## Roadmap

### ✅ Реализовано
- [x] Все 5 методологий (incl. bowtie)
- [x] Авторизация: access JWT + refresh-token rotation в httpOnly cookie
- [x] CSRF protection (signed double-submit)
- [x] Export DOCX
- [x] BowtieDiagram в UI
- [x] `POST /api/v1/upload-report` — автозаполнение формы из DOCX-отчёта
- [x] Извлечение `established_facts` из длинных документов (head + tail + section-aware)

### 🟡 Следующий приоритет
- [ ] Роли: `admin` (все результаты) / `user` (только свои)

### 🟢 Развитие
- [ ] E2E-тесты `pytest` для всех методологий
- [ ] PDF-экспорт
- [ ] Мультиязычный интерфейс (EN/RU)

---

## Статус на 06.06.2026 (v0.5.0)

- ✅ Инфраструктура: Docker Compose (API + PostgreSQL)
- ✅ API: все 5 методологий, refresh/logout, upload-report
- ✅ Авторизация: access JWT + refresh-token rotation в httpOnly cookie, bcrypt
- ✅ CSRF protection: signed double-submit cookie + `X-CSRF-Token`
- ✅ Миграции: 4 версии (001 → 004)
- ✅ Frontend: восстановление сессии, авто-refresh при 401, drag-and-drop загрузка .docx
- ✅ Export DOCX: `GET /api/v1/results/{id}/export` + кнопка ⬇️ DOCX в ResultView.jsx
- ✅ Upload DOCX: `POST /api/v1/upload-report` — автозаполнение формы через LLM (6 497 токенов, 20 полей + victims_list)
- ✅ `established_facts` корректно извлекается из длинных документов — стратегия head + tail + section-aware в `docx_fields_service._trim_text`, `max_tokens=4096`
