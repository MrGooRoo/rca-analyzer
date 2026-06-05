# RCA Analyzer

Веб-приложение для анализа корневых причин (RCA) производственных инцидентов.
Поддерживает 5 методологий, JWT-авторизацию, изолированную историю результатов по пользователям и экспорт отчётов в DOCX.

---

## Стек

| Слой | Технология |
|---|---|
| Backend | FastAPI (Python 3.11) |
| База данных | PostgreSQL + SQLAlchemy + Alembic |
| LLM | OpenRouter → `openai/gpt-4o-mini` |
| Frontend | React (Vite) |
| Контейнеризация | Docker Compose |
| Авторизация | JWT HS256, TTL 24 ч, bcrypt |
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

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/api/v1/auth/register` | Регистрация → JWT |
| POST | `/api/v1/auth/login` | Вход → JWT |
| GET | `/api/v1/auth/me` | Профиль текущего пользователя |

### Анализ (требует Bearer-токен)

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/api/v1/analyze` | Запуск RCA-анализа |
| GET | `/api/v1/results` | История результатов текущего пользователя |
| GET | `/api/v1/results/{id}` | Результат по ID |
| GET | `/api/v1/results/{id}/export` | Скачать DOCX-отчёт |

---

## Экспорт DOCX

Эндпоинт: `GET /api/v1/results/{result_id}/export` (требует Bearer-токен)

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
│   ├── auth/                   # JWT, bcrypt, эндпоинты авторизации
│   ├── api/
│   │   ├── app.py              # CORS, роутеры (v0.3.0)
│   │   └── routes/
│   │       ├── analyze.py      # Защищён Bearer-токеном, пишет user_id
│   │       └── export.py       # GET /results/{id}/export → DOCX
│   ├── db/
│   │   ├── orm_models.py       # UserORM, IncidentORM, RCAResultORM
│   │   └── repository.py       # CRUD
│   ├── domain/
│   │   ├── models.py           # RCAResult, CauseNode, Recommendation
│   │   └── methodologies/      # five_why, ishikawa, rca_systemic, fta, bowtie
│   └── services/
│       ├── analysis_service.py # Оркестратор, реестр _RUNNERS
│       └── export_service.py   # Генерация DOCX (все 5 методологий)
├── frontend/
│   └── src/
│       ├── api.js              # Централизованный fetch; exportDocx() скачивает blob
│       ├── App.jsx             # Login-gate, навигация, logout, обработка 401
│       └── components/
│           ├── AuthPage.jsx        # вход / регистрация
│           ├── HistoryPage.jsx     # история через api.js
│           ├── IncidentForm.jsx    # форма, без прямых HTTP-запросов
│           ├── ResultView.jsx      # кнопка ⬇️ DOCX, без прямых HTTP-запросов
│           ├── BowtieDiagram.jsx   # диаграмма (v6), интегрирована в ResultView
│           └── BowtieDiagram.css   # стили диаграммы (v6)
├── configs/prompts/            # Jinja2-шаблоны: five_why, ishikawa, fta, rca_systemic, bowtie
├── alembic/versions/
│   ├── 001_initial.py
│   ├── 002_fix_varchar_lengths.py
│   └── 003_add_users.py        # users + user_id в incidents/rca_results
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml              # v0.3.0, добавлен python-docx>=1.1
└── .env                        # Создаётся вручную (не в git)
```

---

## Переменные окружения (`.env`)

```env
DATABASE_URL=postgresql+asyncpg://...
OPENROUTER_API_KEY=...
JWT_SECRET=...          # секрет для HS256
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
- **JWT в памяти** (не в localStorage) — при перезагрузке страницы требуется повторный вход
- **user_id** сохраняется в `incidents` и `rca_results`; `GET /api/v1/results` возвращает только записи текущего пользователя
- **OpenRouterClient** создаётся на каждый запрос (`async with`) — предотвращает повторное использование закрытого `httpx.AsyncClient`
- **Frontend HTTP** — вся сетевая логика централизована в `api.js`; компоненты не делают прямых `fetch`-вызовов
- **BowtieDiagram** интегрирован в `ResultView` — автоматически отображается для `methodology === 'bowtie'`; деградированные барьеры выделены визуально
- **Обработка 401 в App.jsx** — при истечении токена автоматический редирект на экран логина
- **Export DOCX** — `export_service.py` генерирует DOCX через `python-docx`; отдельные секции для каждой методологии; защищён Bearer-токеном

---

## Roadmap

### 🟡 Следующий приоритет
- [ ] Refresh-токен / `httpOnly` cookie (сейчас токен в памяти — при перезагрузке нужен повторный вход)
- [ ] Роли: `admin` (все результаты) / `user` (только свои)

### 🟢 Развитие
- [ ] E2E-тесты `pytest` для всех методологий
- [ ] PDF-экспорт (дополнительно к DOCX)
- [ ] Мультиязычный интерфейс (EN/RU)

---

## Статус на 05.06.2026 (v0.3.0)

- ✅ Инфраструктура: Docker Compose (API + PostgreSQL)
- ✅ API: все 6 эндпоинтов работают
- ✅ Авторизация: JWT + bcrypt, защищённые эндпоинты, изоляция данных по пользователю
- ✅ Миграции: 3 версии применены (001 → 002 → 003)
- ✅ Frontend: все компоненты проверены, HTTP через api.js, BowtieDiagram интегрирован
- ✅ Export DOCX: `GET /api/v1/results/{id}/export` + кнопка ⬇️ DOCX в ResultView.jsx
- ✅ **Full smoke-test пройден**: логин → все 5 методологий → скачивание DOCX — всё работает
