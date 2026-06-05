# RCA Analyzer

Веб-приложение для анализа корневых причин (RCA) производственных инцидентов.
Поддерживает 5 методологий, JWT-авторизацию и изолированную историю результатов по пользователям.

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

---

## Быстрый старт

```bash
cd C:\Users\Mr_GooRoo\rca-analyzer
git pull origin main
docker-compose down && docker-compose up -d --build
docker-compose exec api alembic upgrade head
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Методологии

| Методология | Статус | ~Токены |
|---|---|---|
| `five_why` | ✅ работает | ~951 |
| `ishikawa` | ✅ работает | ~2267 |
| `rca_systemic` | ✅ работает | ~1504 |
| `fta` | ✅ работает | ~1446 |
| `bowtie` | ✅ работает + smoke-test пройден | ~3138 |

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

---

## Структура проекта

```
rca-analyzer/
├── src/
│   ├── auth/                   # JWT, bcrypt, эндпоинты авторизации
│   ├── api/
│   │   ├── app.py              # CORS, роутеры
│   │   └── routes/analyze.py   # Защищён Bearer-токеном, пишет user_id
│   ├── db/
│   │   ├── orm_models.py       # UserORM, IncidentORM, RCAResultORM
│   │   └── repository.py       # CRUD
│   ├── domain/
│   │   ├── models.py           # RCAResult, CauseNode, Recommendation
│   │   └── methodologies/      # five_why, ishikawa, rca_systemic, fta, bowtie
│   └── services/
│       └── analysis_service.py # Оркестратор, реестр _RUNNERS
├── frontend/
│   └── src/
│       ├── api.js              # Централизованный fetch с Bearer-токеном
│       ├── App.jsx             # Login-gate, навигация, logout, обработка 401
│       └── components/
│           ├── AuthPage.jsx        # вход / регистрация
│           ├── HistoryPage.jsx     # история через api.js
│           ├── IncidentForm.jsx    # форма, без прямых HTTP-запросов
│           ├── ResultView.jsx      # отображение, без прямых HTTP-запросов
│           ├── BowtieDiagram.jsx   # диаграмма (v6), интегрирована в ResultView
│           └── BowtieDiagram.css   # стили диаграммы (v6)
├── configs/prompts/            # Jinja2-шаблоны: five_why, ishikawa, fta, rca_systemic, bowtie
├── alembic/versions/
│   ├── 001_initial.py
│   ├── 002_fix_varchar_lengths.py
│   └── 003_add_users.py        # users + user_id в incidents/rca_results
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
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

---

## Roadmap

### 🟢 Развитие
- [ ] Export результатов в PDF / Word (`reportlab` или `python-docx`)
- [ ] Refresh-токен / `httpOnly` cookie (сейчас токен в памяти — при перезагрузке нужен повторный вход)
- [ ] Роли: `admin` (все результаты) / `user` (только свои)
- [ ] E2E-тесты `pytest` для всех методологий

---

## Статус на 05.06.2026

- ✅ Инфраструктура: Docker Compose (API + PostgreSQL)
- ✅ API: все 5 методологий работают
- ✅ Авторизация: JWT + bcrypt, защищённые эндпоинты, изоляция данных по пользователю
- ✅ Миграции: 3 версии применены
- ✅ Frontend: все компоненты проверены, HTTP через api.js, BowtieDiagram интегрирован
- ✅ Smoke-test bowtie: выполнен через Swagger UI — диаграмма BowtieDiagram отображает результат корректно (угрозы, барьеры, топ-событие, последствия, деградированные барьеры)
- ✅ Аудит кода: IncidentForm.jsx, ResultView.jsx, App.jsx — голых fetch нет, все запросы через api.js
