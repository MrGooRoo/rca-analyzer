# conventions.md — Соглашения проекта

> Практические правила разработки RCA Analyzer. Если правило меняется — обновить этот файл вместе с кодом.

## 1. Стек

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy async, Alembic.
- **БД:** PostgreSQL 16 + pgvector.
- **LLM:** OpenRouter API.
- **Embeddings:** local / HuggingFace / OpenRouter providers.
- **Frontend:** React 18 + Vite.
- **UI:** CSS + проектный UI-kit, Tailwind utilities без reset.
- **Auth:** JWT access/refresh в httpOnly cookie, CSRF signed double-submit, роли `admin/user`.
- **Export:** python-docx, fpdf2.
- **Контейнеризация:** Docker Compose.

## 2. Нейминг

| Что | Формат | Пример |
|---|---|---|
| Python modules/files | `snake_case` | `analysis_service.py` |
| Python classes | `PascalCase` | `RCARepository` |
| Python functions | `snake_case` | `create_session()` |
| Constants | `UPPER_SNAKE_CASE` | `CSRF_COOKIE_NAME` |
| React components | `PascalCase.jsx` | `IncidentForm.jsx` |
| React hooks | `useSomething` | `useAuth()` |
| CSS classes | kebab / BEM-like | `analysis-result-toolbar__title` |
| API endpoints | `/api/v1/...` | `/api/v1/results/compare` |
| DB tables | `snake_case` plural | `analysis_sessions` |

## 3. Язык

- Документация: русский.
- Пользовательские сообщения UI: русский.
- Комментарии в коде: русский допустим, особенно для бизнес-логики.
- Имена переменных, функций, классов: английский.
- Commit messages: английский, Conventional Commits style.

Примеры:

```text
feat(frontend): allow cancelling active analysis
fix(api): preserve session id in compare results
test(api): remove httpx deprecation warnings in csrf tests
docs: update architecture and methodology docs
```

## 4. Backend conventions

- Роуты FastAPI живут в `src/api/routes/`.
- Бизнес-сценарии — в `src/services/`, не в роутерах.
- Работа с БД — через `RCARepository`, не напрямую из UI/API-слоя.
- Pydantic-модели и доменные типы — в `src/domain/models.py`.
- Методики RCA наследуют `MethodologyRunner`.
- Prompts хранятся в `configs/prompts/*.j2`, не в Python-коде.
- Фиксированные маршруты объявлять до параметризованных, например `/results/compare` до `/results/{result_id}`.

## 5. Frontend conventions

- Все HTTP-вызовы — через `frontend/src/api.js`.
- Авторизация — только через `AuthContext` / `useAuth()`.
- Ошибки и пользовательские уведомления — через `useToast()`.
- Формы и кнопки по возможности используют UI-kit:
  - `Button`;
  - `Input`, `Textarea`, `Select`;
  - `Card`, `Badge`.
- Нативные controls допустимы для специальных случаев: file input, radio, checkbox-card UI.
- Во время анализа форма получает `loading` и блокируется через общий флаг `busy`.

## 6. Auth / CSRF conventions

- Access/refresh tokens хранятся в httpOnly cookie.
- Для unsafe HTTP-методов frontend отправляет `X-CSRF-Token` из `csrf_token` cookie.
- Перед login/register frontend вызывает `GET /api/v1/auth/csrf`.
- При 401 API-клиент один раз пробует refresh; если не помогло — вызывает global auth-lost handler.
- CSRF-тесты используют явный `httpx.ASGITransport`, без deprecated shortcuts.

## 7. Analysis sessions conventions

- Каждый `/analyze`, `/analyze-multi`, `/analyze-multi-stream` создаёт новую `analysis_session`.
- Multi-analysis всегда сохраняет все методики в одну сессию.
- История UI загружается через `/sessions`, не через плоский `/results`.
- Compare предпочитает `session_id`; `incident_id` остаётся fallback для старых данных.

## 8. Embeddings conventions

- В `result_embeddings.model_name` пишется фактическая модель, построившая вектор.
- Поиск похожих сравнивает только embeddings с тем же `model_name`.
- При ошибке внешнего provider repository откатывается на local provider.
- После смены provider переиндексация старых результатов происходит лениво.

## 9. Документация

После значимых изменений обновлять:

- `docs/state.md` — текущее состояние;
- `docs/contracts.md` — если меняется API/data/frontend contract;
- `README.md` — если меняется запуск или пользовательские возможности;
- профильный документ (`architecture.md`, `methodologies.md`, `conventions.md`) — если меняется соответствующая область.

## 10. Проверки перед коммитом

Стандартный набор:

```bash
ruff check
python -m pytest tests/ -q
npm --prefix frontend run build
```

Для docs-only изменений достаточно проверить, что патч применим и Markdown не ломает смысл, но если изменение затрагивает код — прогонять полный набор.
