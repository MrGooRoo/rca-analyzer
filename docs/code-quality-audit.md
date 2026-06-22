# code-quality-audit.md — Аудит качества кода RCA Analyzer

> **Дата:** 2026-06-15  
> **Охват:** backend (FastAPI, domain, DB, integrations), frontend (React), тесты, безопасность.  
> **Связанные документы:** [architecture.md](architecture.md), [state.md](state.md), [refactoring-plan-sse-db.md](refactoring-plan-sse-db.md).

---

## 1. Резюме

| Критерий | Оценка | Комментарий |
|----------|--------|-------------|
| Архитектура | 8/10 | Слои разделены, есть `contracts.md` |
| Backend | 7/10 | Сильный LLM-клиент; слабые транзакции и SSE |
| Frontend | 6.5/10 | Хороший UX отмены; монолиты, нет тестов |
| Безопасность | 6/10 | CSRF + RBAC; дефолтные секреты |
| Тестирование | 7.5/10 | ~257 тестов; нет SSE и DB integration |
| Документация | 9/10 | Контракты и state ведутся актуально |

**Вердикт:** проект выше среднего для LLM-приложения такого масштаба. Основной техдолг сосредоточен в узких зонах (SSE + БД, границы транзакций, рост frontend).

---

## 2. Сильные стороны

### 2.1. Контрактно-ориентированная разработка

`docs/contracts.md` — единый источник правды для API, Pydantic и frontend. Снижает рассинхрон между слоями.

### 2.2. Разделение слоёв

- Domain не зависит от FastAPI.
- Промпты в `configs/prompts/*.j2`.
- Методики — плагины через `MethodologyRunner`.
- Интеграции изолированы в `src/integrations/`.

### 2.3. LLM-клиент (`src/integrations/llm/openrouter.py`)

Retry с backoff, fallback-модели, валидация JSON, whitelist моделей без `json_object`, context manager для httpx.

### 2.4. Embeddings

Три провайдера (local v2, HuggingFace, OpenRouter) с фабрикой, автофолбэком, фильтрацией по `model_name`, lazy backfill.

### 2.5. Auth и CSRF

httpOnly cookies, refresh rotation, signed double-submit CSRF, RBAC admin/user.

### 2.6. Frontend: отмена анализа

`AbortController` + `analysisRunRef`, `beforeunload`, confirm при уходе со страницы во время анализа.

### 2.7. Тесты

Unit (методики, compare, embeddings), API (analyze, sessions, CSRF, roles), integration e2e всех 5 методик с FakeLLM.

---

## 3. Критические проблемы (P0)

| # | Проблема | Где | Статус |
|---|----------|-----|--------|
| P0-1 | `incident_id=str(incident_date)` во всех runners → `"None"` при пустой дате | `src/domain/methodologies/*.py` | ✅ Исправлено 15.06.2026 |
| P0-2 | SSE держит DB-сессию на время LLM → истощение пула | `analyze.py` `analyze_multi_stream` | ✅ Исправлено 15.06.2026 |
| P0-3 | SSE: результат в `done` при ошибке `save_result` | `analyze.py:266–283` | ✅ Исправлено 15.06.2026 |
| P0-4 | `SimilarIncidentsHint.css` не импортируется | `SimilarIncidentsHint.jsx` | ✅ Исправлено 15.06.2026 |
| P0-5 | Дефолтный `JWT_SECRET` без fail-fast в prod | `src/auth/service.py` | ⏳ P1 |

---

## 4. Серьёзные проблемы (P1)

### Backend

| Проблема | Файл | Риск |
|----------|------|------|
| `asyncio.gather` без `return_exceptions=True` в `analyze_multi` | `analysis_service.py` | Средний |
| Commit внутри `repository.save_result()` + commit в роуте | `repository.py`, `analyze.py` | Средний |
| Repository импортирует `embedding_service` (DB → services) | `repository.py` | Средний |
| `list_sessions` over-fetch (все results + nodes) | `repository.py` | Средний |
| `error_one` отдаёт `str(exc)` клиенту | `analyze.py` | Средний |
| `Recommendation.status` пишется, но не читается в domain | `repository.py` | Низкий |
| Нет `max_length` на `title`/`description` | `models.py` | Средний |

### Frontend

| Проблема | Файл | Риск |
|----------|------|------|
| `App.jsx` — god-component (~15 useState) | `App.jsx` | Средний |
| `IncidentForm.jsx` — монолит ~550 строк | `IncidentForm.jsx` | Средний–высокий |
| `ResultView` без optional chaining | `ResultView.jsx` | Средний |
| Дублирование auth state (`api.js` + `AuthContext`) | оба | Низкий–средний |
| Нет frontend-тестов, TypeScript, ESLint | `frontend/` | Средний |

### Тесты

| Пробел | Риск |
|--------|------|
| Нет integration-тестов repository + PostgreSQL/pgvector | Средний |
| Нет unit-тестов `BowtieRunner` | Низкий |
| Дублирование `test_openrouter.py` + `test_openrouter_client.py` | Низкий |

---

## 5. Архитектурные расхождения

```text
[Соответствует]  Frontend → API → Services → Domain → Integrations
[Расхождение]    API → RCARepository напрямую (персистенция в HTTP-слое)
[Расхождение]    Repository → embedding_service (обратная зависимость слоёв)
```

Детальный план по блоку SSE/БД: [refactoring-plan-sse-db.md](refactoring-plan-sse-db.md).

---

## 6. Безопасность

| Аспект | Статус |
|--------|--------|
| CSRF double-submit | ✅ |
| httpOnly cookies | ✅ |
| CSRF + RBAC | ✅ |
| Refresh rotation | ✅ |
| Rate limiting / captcha на register | ✅ (in-memory sliding window) |
| Account lockout | ✅ (5 попыток → 15 мин блокировки) |
| max_length на полях title/description | ✅ (Pydantic Field(max_length=...)) |
| Роль из JWT, не из БД на каждый запрос | ⚠️ |
| `COOKIE_SECURE=false` по умолчанию | ⚠️ prod |
| Пароль min 6 символов | ⚠️ |

---

## 7. Приоритетный план

### Быстрые wins (1–2 дня)

1. ~~Исправить `incident_id` в runners~~ ✅
2. ~~SSE: не добавлять в `results` при ошибке save~~ ✅
3. ~~Импорт `SimilarIncidentsHint.css`~~ ✅
4. Optional chaining в `ResultView`
5. Fail-fast на дефолтный `JWT_SECRET` в prod

### Средний срок (1–2 недели)

6. ~~SSE: короткоживущие DB-сессии~~ ✅ (базовая реализация)
7. Unit of Work: единое место commit
8. Тесты на SSE (`/analyze-multi-stream`)
9. `gather(..., return_exceptions=True)` в `analyze_multi`
10. Разбить `App.jsx` / `IncidentForm.jsx`

### Долгосрочно

11. Персистенция в `AnalysisService` или use-case слой
12. TypeScript / Vitest на frontend
13. Решить судьбу Tailwind (использовать или удалить)
14. Integration-тесты PostgreSQL + pgvector в CI

---

## 8. Общий вывод

Проект с осознанной архитектурой и сильной интеграцией LLM/embeddings. Главные риски — SSE/БД (частично закрыты в P0), границы транзакций, рост frontend без типов и тестов. Для внутреннего инструмента с умеренной нагрузкой — готов к использованию после P0/P1.
