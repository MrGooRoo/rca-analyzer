# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении.

## Статус: 🟡 Стабильно — чистка аудита: Recommendation.status, DB lengths, embedding DI, Literal статусов, owner check

**Дата обновления:** 2026-06-23

**ВАЖНО:** CI пока настроен без mypy (131 error требует отдельной чистки). Frontend build требует `npm install` (зависимости не стянуты в этой сессии).

## Рефакторинг: PersistenceService — полноценный use-case слой (22.06.2026)
- [x] `_save_kwargs()` helper — единое место для save_result kwargs (убрано дублирование)
- [x] `_SessionManager` — контекстный менеджер сессии с rollback (вместо __aenter__/__aexit__ вручную)
- [x] Read-операции (get_result, list_results, get_session, list_sessions)
  и delete/update тоже через PersistenceService — полное единообразие
- [x] CI: добавлен `cache: pip` и `cache: npm` — ускорение установки зависимостей
- [x] analyze.py: -36% строк (467 → 299), все эндпоинты через _persistence

## P0 Security: Rate limiting + Account lockout (22.06.2026)
- [x] In-memory rate limiter: `src/api/middleware/rate_limiter.py` — sliding window, 10 запросов за 15 минут по IP
- [x] Rate limiter подключён к `/login` и `/register` через FastAPI Depends
- [x] Account lockout: `failed_login_attempts` + `locked_until` поля в `users` таблице
- [x] После 5 неудачных попыток входа аккаунт блокируется на 15 минут
- [x] После истечения блокировки счётчик сбрасывается
- [x] При успешном входе счётчик обнуляется
- [x] Миграция Alembic 014
- [x] Настройки через env: `MAX_FAILED_LOGIN_ATTEMPTS`, `LOCKOUT_MINUTES`, `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`
- [x] Проверки: 285 passed, ruff clean

## P1: max_length + .env.example + CI (22.06.2026)
- [x] Добавлены `max_length` на все строковые поля в `Victim` и `IncidentInput` (Pydantic)
- [x] Обновлён `.env.example` — добавлены секции rate limiting и account lockout
- [x] GitHub Actions CI: `.github/workflows/ci.yml` — pytest + ruff + npm build на каждый push/PR

## Frontend: общий проход по Tailwind-остаткам (21.06.2026)
- [x] Найдены и переведены последние Tailwind-подобные `className` в:
  `AnalysisProgress.jsx`, `SingleAnalysisProgress.jsx`, `BowtieDiagram.jsx`,
  `SimilarIncidentsHint.jsx`, `HistoryPage.jsx`.
- [x] Добавлены семантические CSS-файлы:
  `AnalysisProgress.css`, `SingleAnalysisProgress.css`, `BowtieDiagram.css`,
  `SimilarIncidentsHint.css`, `HistoryPage.css`.
- [x] Удалён временный `frontend/src/tailwind-compat.css` и импорт из `index.css`.
- [x] Сканер Tailwind-подобных классов показал: `tailwind-like residues: 0`.
- [x] Проверки: `npm run build` во frontend → успешно; `git diff --check` → OK.

## Инфраструктура
- Репозиторий: `MrGooRoo/rca-analyzer`
- Docker Compose: `rca-analyzer-api-1` (FastAPI) + PostgreSQL с pgvector
  - DB image: `pgvector/pgvector:pg16`
- LLM: текущий runtime — OpenRouter через `OpenRouterClient`; п.17 планирует admin-настройки `draft_model`/`verifier_model` вместо жёсткой модели в коде
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
- [x] **Сущность «исследование» в БД** (13.06.2026)
  - ✅ Таблица `analysis_sessions` (id, created_at, user_id, incident_title, incident_description,
    incident_date, incident_location, incident_type, incident_severity, incident_data_json)
  - ✅ FK `rca_results.session_id` → `analysis_sessions.id` (nullable, с индексом)
  - ✅ Миграция Alembic 008 с backfill: для каждого incident_id создаётся сессия,
    все результаты с этим incident_id получают session_id
  - ✅ Pydantic-модель `AnalysisSession` + `session_id` в `RCAResult`
  - ✅ Repository: `create_session()`, `get_session()`, `list_sessions()`, `list_results_by_session()`
  - ✅ API: `GET /sessions`, `GET /sessions/{session_id}`, обновлён `/results/compare`
    (принимает `session_id` и `incident_id`; session_id приоритетнее)
  - ✅ `/analyze`, `/analyze-multi`, `/analyze-multi-stream` — создают сессию при каждом запросе
  - ✅ Frontend: `api.sessions`, `compareResults(incidentId, sessionId)`,
    `groupByIncident()` группирует по `session_id` (fallback на `incident_id`)
  - ✅ Тесты: 15 новых (юнит + API), всего 250 passed
  - ✅ Обновлены contracts.md (раздел 15) и state.md
- [x] **Docker-интеграция HF-эмбеддингов** (13.06.2026)
  - ✅ Dockerfile: target `prod-embeddings` (torch CPU + transformers)
  - ✅ Dockerfile: target `dev-embeddings` для разработки
  - ✅ docker-compose.yml: named volume `hf_cache` для `HF_HOME`
  - ✅ app.py lifespan: прогрев модели при `EMBEDDINGS_PROVIDER=huggingface`
  - ✅ `.env.example`: уточнена документация HF_HOME
- [x] **UX похожих инцидентов** (13.06.2026)
  - ✅ Клик по карточке → загружает полный RCAResult из БД и открывает его
  - ✅ Фильтры по методике и диапазону дат
  - ✅ Цветные бейджи похожести (🟢 ≥75%, 🟡 ≥50%, 🔴 <50%)
  - ✅ Кнопка «Открыть →» на кликабельных карточках
  - ✅ Лимит похожих увеличен до 10
  - ✅ App.jsx: `handleSubmitMulti` использует `session_id`
- [x] **Фикс HTTP 431 в поиске похожих** (11.06.2026)
  - ✅ Новый `POST /api/v1/incidents/similar` — текст в теле запроса (`SimilarIncidentsRequest`)
  - ✅ GET-вариант оставлен как deprecated (обратная совместимость)
  - ✅ `frontend/src/api.js`: querySimilarIncidents переведён на POST
  - ✅ +5 тестов: POST happy-path, длинный текст 5000 символов, excludes, валидация (422)
- [x] **incident_hash + фильтр повторных анализов из «похожих»** (13.06.2026)
  - ✅ SHA-256 отпечаток (`incident_hash`) от title+description в `analysis_sessions`
  - ✅ Миграция 009: добавляет `incident_hash` с backfill
  - ✅ `save_result()` принимает `incident_title`, `incident_description` и др. — API передаёт реальные данные
  - ✅ `find_similar_incidents()`: параметр `exclude_incident_hash` — исключает сессии с тем же отпечатком
  - ✅ `SimilarIncidentsRequest`: `incident_title`+`incident_description` для дедупа из формы
  - ✅ `_do_find_similar()`: вычисляет hash из формы, передаёт `exclude_incident_hash`
  - ✅ Старые сессии с `incident_title="—"` скрыты из «похожих» (неизвестный инцидент — не «похожий»)
  - ✅ Миграция 010: чинит placeholder-данные старых сессий, извлекая из `incident_data_json`
  - ✅ Frontend: `IncidentForm` передаёт `form.title`/`form.description` в SimilarIncidentsPanel
- [x] **Контекст инцидента в карточках «похожих»** (13.06.2026)
  - ✅ `SimilarIncident` модель: добавлены `incident_title`, `incident_description`, `incident_date`, `incident_location` (из сессии)
  - ✅ `_orm_to_similar()`: подгружает `session` и передаёт данные инцидента
  - ✅ SQL-запросы поиска похожих: добавлен `selectinload(RCAResultORM.session)`
  - ✅ `SimilarCard`: визуальный блок с заголовком, описанием, датой и местом инцидента (голубая полоска слева)
  - ✅ +1 тест: `test_similar_incidents_include_incident_context`
- [x] **Блокировка формы при анализе/загрузке DOCX** (13.06.2026)
  - ✅ Переменная `busy = loading || uploading` — единый флаг блокировки
  - ✅ Все поля формы (input, textarea, select, radio, checkbox) получают `disabled={busy}`
  - ✅ Кнопки «Добавить пострадавшего», «Сбросить DOCX» тоже заблокированы
  - ✅ Зона загрузки DOCX не реагирует на клик при `busy`
  - ✅ `SimilarIncidentsPanel` получает `disabled={busy}` — поиск похожих заблокирован
  - ✅ CSS: заблокированные поля полупрозрачные (opacity 0.55), курсор not-allowed
- [x] **Индикатор похожих в форме, полный блок в результате** (13.06.2026)
  - ✅ `SimilarIncidentsHint` — лёгкий индикатор-счётчик в форме: «🔗 Найдено 3 похожих инцидента»
  - ✅ Полный блок `SimilarIncidentsPanel` — только в ResultView (автопоиск после анализа)
  - ✅ Нет дублей: одна строчка в форме, полный блок в результате
- [x] **UI-kit + Tailwind-совместимость + Toast + AuthContext** (13.06.2026)
  - ✅ Tailwind CSS v4: @tailwindcss/vite плагин, только utilities (без reset — не ломает существующие стили)
  - ✅ cn() утилита: clsx + tailwind-merge для корректного слияния классов
  - ✅ Button: варианты primary/secondary/ghost/danger/outline, размеры sm/md/lg, loading-спиннер
  - ✅ Card + CardBody + CardHeader + Badge: тонированные бейджи (7 цветов)
  - ✅ Field: Input, Textarea, Select с label/hint/error
  - ✅ Toast + ToastProvider + useToast: уведомления info/success/error/warning с автозакрытием
  - ✅ methodologies.js: метаданные методологий (иконки, описания, цвета)
  - ✅ AuthContext: чистая архитектура авторизации (login/register/logout/refresh)
  - ✅ main.jsx: обёрнуто в AuthProvider + ToastProvider
  - ✅ `tailwind-compat.css`: временный слой совместимости для старых Tailwind-классов после удаления зависимости
- [x] **App.jsx мигрирован на UI-kit** (14.06.2026)
  - ✅ `useAuth()` из AuthContext: убрана дублирующая auth-логика
  - ✅ `useToast()` вместо `<div className="alert alert-error">`
  - ✅ Навигационные кнопки → `<Button variant="ghost">`
  - ✅ Кнопка «Выйти» → `<Button variant="secondary" size="sm">`
  - ✅ Кнопка «← Назад в историю» → `<Button variant="secondary" size="sm">`
  - ✅ `AuthContext` регистрирует `setAuthLostHandler` — при любом 401 user сбрасывается в null
  - ✅ `AuthPage.jsx`: убран проп `onAuth`, напрямую `useAuth().login/register`
  - ✅ `App.css` почищен: удалены `.nav-btn`, `.nav-btn--active`, `.btn-logout`, `.btn-back`, `.alert-error`
- [x] **AuthPage.jsx мигрирован с Tailwind-классов на чистый CSS** (20.06.2026)
  - ✅ `AuthPage.jsx`: заменены `min-h-screen/flex/.../bg-slate-...` на семантические классы
  - ✅ Добавлен `frontend/src/components/AuthPage.css`
  - ✅ Экран входа визуально сохранён: центральная карточка, переключатель «Вход/Регистрация», поля и кнопка
  - ✅ Проверка: `npm run build` во frontend → успешно
  - ✅ Скриншот: `/root/rca-preview/authpage-clean.png`
- [x] **IncidentForm.jsx мигрирован с Tailwind-классов на чистый CSS** (20.06.2026)
  - ✅ `IncidentForm.jsx`: заменены старые Tailwind-классы на семантические CSS-классы
  - ✅ Добавлен `frontend/src/components/IncidentForm.css`
  - ✅ Сохранены блоки: способ заполнения, DOCX upload, обстоятельства, фото, пострадавшие, классификация и параметры анализа
  - ✅ Проверка: `npm run build` во frontend → успешно
- [x] **AdminPage.jsx мигрирован с Tailwind-классов на чистый CSS** (20.06.2026)
  - ✅ `AdminPage.jsx`: заменены старые Tailwind-классы на семантические CSS-классы
  - ✅ Добавлен `frontend/src/components/AdminPage.css`
  - ✅ Сохранены блоки: LLM Conductor, поиск моделей, настройки draft/verifier, таблица пользователей
  - ✅ Проверка: `npm run build` во frontend → успешно
- [x] **CompareView.jsx мигрирован с Tailwind-классов на чистый CSS** (20.06.2026)
  - ✅ `CompareView.jsx`: заменены старые Tailwind-классы на семантические CSS-классы
  - ✅ Добавлен `frontend/src/components/CompareView.css`
  - ✅ Сохранены блоки: заголовок сравнения, сводка, общие рекомендации, различающиеся выводы, табы и детальный результат
  - ✅ Проверка: `npm run build` во frontend → успешно
- [x] **ResultView.jsx мигрирован с Tailwind-классов на чистый CSS** (20.06.2026)
  - ✅ `ResultView.jsx`: заменены старые Tailwind-классы на семантические CSS-классы
  - ✅ Добавлен `frontend/src/components/ResultView.css`
  - ✅ Сохранены блоки: шапка результата, экспорт, сводка, похожие инциденты, табы, дерево причин, рекомендации и мета
  - ✅ Проверка: `npm run build` во frontend → успешно
- [x] **AnalysisSteps.jsx мигрирован с Tailwind-классов на чистый CSS** (20.06.2026)
  - ✅ `AnalysisSteps.jsx`: заменены старые Tailwind-классы на семантические CSS-классы
  - ✅ Добавлен `frontend/src/components/AnalysisSteps.css`
  - ✅ Сохранены блоки: sticky-навигация по шагам, состояния done/active/pending и переход к секциям формы
  - ✅ Проверка: `npm run build` во frontend → успешно
- [x] **SimilarIncidentsPanel.jsx мигрирован с Tailwind-классов на чистый CSS** (20.06.2026)
  - ✅ `SimilarIncidentsPanel.jsx`: заменены старые Tailwind-классы на семантические CSS-классы
  - ✅ Добавлен `frontend/src/components/SimilarIncidentsPanel.css`
  - ✅ Сохранены блоки: заголовок, поиск, фильтры, статусы загрузки/ошибки, список похожих карточек
  - ✅ Проверка: `npm run build` во frontend → успешно
- [x] **P2/P6 — явные UI-состояния анализа** (14.06.2026)
  - ✅ Страница анализа разделена на состояния: ВВОД → АНАЛИЗ → РЕЗУЛЬТАТ
  - ✅ После результата `IncidentForm` скрывается, не смешивается с результатом
  - ✅ Над `ResultView`/`CompareView` добавлена панель с кнопкой «➕ Новый анализ»
  - ✅ В просмотре результата из истории: «Назад в историю» и «Новый анализ»
- [x] **IncidentForm.jsx — поля на UI-kit** (14.06.2026)
  - ✅ Основные поля на `Input`, `Textarea`, `Select` из `components/ui/Field.jsx`
  - ✅ Счётчики по коду: `<Input>` 26, `<Textarea>` 6, `<Select>` 5; нативные `<textarea>/<select>` отсутствуют
- [x] **HistoryPage.jsx — UI-kit миграция** (14.06.2026)
  - ✅ Карточки на `Card` из UI-kit, фильтры на `Input`/`Select`, кнопки на `Button`
  - ✅ `Card`/`CardHeader`/`CardBody` пробрасывают DOM props (`onClick`, `title`)
  - ✅ Счётчики: `<Card>` 2, `<Button>` 5, `<Input>` 1, `<Select>` 3; нативные отсутствуют
- [x] **HistoryPage.jsx — загрузка через `/sessions` API** (14.06.2026)
  - ✅ История через `api.sessions.list(PAGE_SIZE, offset)` вместо `api.results.list(...)`
  - ✅ Пагинация по исследованиям (`analysis_sessions`)
  - ✅ Сравнение методик не разрывается между страницами
- [x] **SimilarIncidentsPanel.jsx — UI-kit миграция** (14.06.2026)
  - ✅ Кнопки на `Button`, фильтры на `Select`/`Input`, карточки на `Card`/`Badge`
  - ✅ Счётчики: `<Button>` 4, `<Input>` 2, `<Select>` 1, `<Card>` 1, `<Badge>` 4; нативные отсутствуют

## Проверки
- `python -m pytest tests/ -q` → **285 passed, 1 deselected (slow)**
- `pytest -m slow -o addopts=""` (реальная rubert-tiny2) → **1 passed**
- `ruff check` → **All checks passed!**
- `npm run build` во frontend → **успешно**

- [x] **AnalysisProgress.jsx — SSE-прогресс multi-analysis** (14.06.2026)
  - ✅ Multi-analysis через `api.analyzeMultiStream()` / `POST /api/v1/analyze-multi-stream`
  - ✅ `AnalysisProgress` на Apple-style dark UI с `Card`/`Badge`, прогресс-баром и состояниями running/done/error

- [x] **P3 — предупреждение при уходе во время анализа** (14.06.2026)
  - ✅ `window.confirm` при переходе из активного анализа
  - ✅ При подтверждённом уходе UI отвязывается от in-flight запроса
  - ✅ `beforeunload`-предупреждение при закрытии вкладки во время анализа

- [x] **P4 — отмена анализа через AbortController** (14.06.2026)
  - ✅ `api.req()` принимает `signal`, прокидывает в `fetch`
  - ✅ `api.analyze`, `api.analyzeMulti`, `api.analyzeMultiStream` поддерживают отмену
  - ✅ Панель «⏹ Отменить анализ» под формой
  - ✅ `AbortError` не показывается как ошибка

- [x] **Техдолг — httpx deprecation warnings в CSRF-тестах** (14.06.2026)
- [x] **Документация — закрыты TODO-заглушки** (14.06.2026)
  - `docs/architecture.md`, `docs/conventions.md`, `docs/methodologies.md`

- [x] **Feedback #1 / #1.1 — логика ручного ввода и DOCX-дозаполнения** (14.06.2026)
- [x] **Feedback #2/#3 — placeholder-подсказки и удаление реальных примеров** (14.06.2026)

- [x] **Feedback #15 — статус выполнения для одиночного анализа** (16.06.2026)
  - ✅ Backend: `POST /api/v1/analyze-stream` — SSE-эндпоинт для одиночного анализа с этапами
    `started → preparing → llm → parsing → done/error` и процентами 0/10/40/80/100.
  - ✅ `AnalysisService.analyze_stream()` — асинхронный генератор событий; обрабатывает
    `MethodologyNotSupportedError`, `LLMResponseValidationError` и неожиданные ошибки.
  - ✅ Frontend: `api.analyzeStream()` в `api.js` — клиент для SSE, аналогичный `analyzeMultiStream`.
  - ✅ Frontend: компонент `SingleAnalysisProgress.jsx`/`SingleAnalysisProgress.css` — карточка
    прогресса с методикой, иконкой, прогресс-баром и текущим этапом.
  - ✅ `App.jsx` переключил одиночный анализ на `api.analyzeStream`; добавлено состояние
    `singleProgress`; отмена через `AbortController` работает для SSE-одиночного анализа так же, как для multi.
  - ✅ Тесты: `tests/api/test_analyze_stream.py` (4 теста), `tests/unit/test_analysis_service.py`
    (+3 теста на stream). Итого: **268 passed, 1 deselected**.
  - ✅ Обновлены `docs/contracts.md` (разделы 10.2, 10.4, 10.4.3, 15.6) и `docs/user-feedback-backlog.md`.

- [x] **Feedback #16 — оптимизация скорости обработки** (16.06.2026)
  - ✅ `OpenRouterClient` переиспользует общий `httpx.AsyncClient` между экземплярами в процессе
    (keep-alive / connection reuse), вместо создания нового HTTP-клиента на каждый LLM-запрос.
  - ✅ Добавлены счётчик ссылок и `asyncio.Lock` для безопасного жизненного цикла shared client.
  - ✅ Лимиты соединений: `max_connections=20`, `max_keepalive_connections=10`.
  - ✅ Shutdown FastAPI вызывает `OpenRouterClient.close_shared()`.
  - ✅ Временный файл `p16-only.patch` удалён из репозитория.
  - ✅ Финальная проверка после cleanup: **269 passed, 1 deselected**, targeted `ruff check` — **All checks passed!**
  - Коммиты: `a686cf6`, `798c172`, `d00e251`, cleanup `72e84b2`.

- [x] **Feedback #17 — LLM Conductor: бесплатный черновик + дешёвый верификатор** (17.06.2026)
  - 📌 Подробная архитектура: [`docs/p17-llm-conductor-plan.md`](p17-llm-conductor-plan.md).
  - Решение: это не простой fallback и не «подмешивание» моделей, а дирижирование:
    `draft_model` делает основной RCA-анализ, `verifier_model` проверяет/улучшает черновик только по схеме.
  - Основной режим: `verification_scheme="threshold"` — verifier вызывается, если
    `draft_result.confidence_avg < quality_threshold` (default `0.70`).
  - Настройки должен менять admin в кабинете, без хардкода в Python: `draft_model`, `verifier_model`,
    `quality_threshold`, `verification_scheme`.
  - Рекомендуемое хранение: новая singleton-таблица `llm_settings` (`id=1`) с типизированными полями,
    DB-валидацией и аудитом `updated_at`/`updated_by`.
  - Желательный выбор моделей: backend proxy к публичному каталогу OpenRouter
    `GET https://openrouter.ai/api/v1/models`, autocomplete/select в админке; ручной ввод slug остаётся fallback.
  - Дешёвые verifier-кандидаты: `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, их `:free` варианты,
    `openai/gpt-4o-mini`, `google/gemini-2.5-flash-lite` — конкретные цены показывать live из OpenRouter.
  - Верификатор не делает полный анализ заново: получает IncidentInput + methodology + draft JSON + low-confidence узлы
    и возвращает тот же JSON-контракт для существующих methodology runners.
  - Порядок реализации: settings DB/API → OpenRouter catalog → Admin UI → verifier prompt → `LLMConductor`
    → интеграция в `AnalysisService.analyze()` и `analyze_stream()` → аудит токенов/моделей.
  - ✅ Этап 1 реализован (17.06.2026): `llm_settings` singleton-таблица, ORM, Pydantic-схемы,
    `LLMSettingsRepository`, admin-only `GET/PUT /api/v1/admin/llm-settings`, API-тесты.
  - ✅ Проверки этапа 1: `pytest tests/api/test_admin.py tests/api/test_admin_llm_settings.py -q` → **13 passed**;
    `python -m pytest tests/ -q` → **274 passed, 1 deselected**; targeted `ruff check` → **All checks passed!**
  - ✅ Этап 2 реализован (17.06.2026): `GET /api/v1/admin/openrouter/models` — admin-only backend proxy
    к публичному каталогу `https://openrouter.ai/api/v1/models` с in-memory cache, фильтрами `search/free_only/limit`
    и безопасным ответом `OpenRouterModelInfo[]` для будущего select/autocomplete в админке.
  - ✅ Проверки этапа 2: `pytest tests/api/test_admin.py tests/api/test_admin_llm_settings.py tests/api/test_admin_openrouter_models.py -q`
    → **17 passed**;
    `python -m pytest tests/ -q` → **278 passed, 1 deselected**; targeted `ruff check` → **All checks passed!**
  - ✅ Этап 3 реализован (17.06.2026): в `AdminPage` добавлен блок **LLM Conductor** для настройки
    `draft_model`, `verifier_model`, `quality_threshold`, `verification_scheme`; модели выбираются через
    `api.admin.openRouterModels()` с `datalist` и ручным fallback, если каталог недоступен.
  - ✅ Проверки этапа 3: `cd frontend && npm run build` → **успешно**;
    `python -m pytest tests/ -q` → **278 passed, 1 deselected**.
  - ✅ Этап 4 реализован (17.06.2026): `configs/prompts/verifier.j2` — prompt для дешёвой verifier-модели,
    которая проверяет draft RCA JSON, low-confidence узлы и рекомендации без полного повторного анализа.
  - ✅ `PromptRenderer.render()` поддерживает `extra_context`, чтобы будущий `LLMConductor` мог передать
    `draft_result_json`, `low_confidence_nodes`, `methodology`, `output_schema_hint`.
  - ✅ Проверки этапа 4: `pytest tests/unit/test_prompt_renderer.py -q` → **10 passed**;
    `python -m pytest tests/ -q` → **280 passed, 1 deselected**; targeted `ruff check` → **All checks passed!**
  - ✅ Этап 5 реализован (17.06.2026): `src/services/llm_conductor.py` — standalone-сервис
    `draft_model → threshold gate → verifier_model → final RCAResult`, с суммированием токенов и `model_used="draft -> verifier"`.
  - ✅ Unit-тесты `tests/unit/test_llm_conductor.py`: disabled, threshold skip, threshold verify, always verify.
  - ✅ Проверки этапа 5: `pytest tests/unit/test_llm_conductor.py -q` → **4 passed**;
    `python -m pytest tests/ -q` → **284 passed, 1 deselected**; targeted `ruff check` → **All checks passed!**
  - ✅ Этап 6 реализован (17.06.2026): `LLMConductor` подключён к реальному pipeline:
    `AnalysisService.analyze()`, `analyze_stream()`, `analyze_multi()` и API-роуты single/multi/SSE передают `llm_settings`.
    Если настройки недоступны, используется legacy pipeline без падения анализа.
  - ✅ Проверки этапа 6: `pytest tests/unit/test_analysis_service.py -q` → **9 passed**;
    API analyze tests → **15 passed**; `python -m pytest tests/ -q` → **285 passed, 1 deselected**; targeted `ruff check` → **All checks passed!**
  - ✅ Этап 7 реализован (17.06.2026): расширенный audit/provenance моделей и токенов:
    `draft_model_used`, `verifier_model_used`, `draft_tokens_used`, `verifier_tokens_used`,
    `verification_applied`, `verification_reason` в `RCAResult` и `rca_results` (migration `012`).
  - ✅ `LLMConductor` заполняет provenance для draft-only и verified сценариев; `tokens_used` остаётся суммарным.
  - ✅ Проверки этапа 7: `pytest tests/unit/test_llm_conductor.py -q` → **4 passed**;
    `python -m pytest tests/ -q` → **285 passed, 1 deselected**; targeted `ruff check` → **All checks passed!**
  - ✅ Stability fix (17.06.2026): расширены DB-колонки LLM-generated ids до `VARCHAR(200)`
    (`causal_nodes.node_id/parent_id`, `recommendations.rec_id/cause_id`), чтобы сохранять id с префиксами
    вроде `imm-<uuid>`, `contrib-<uuid>`, `r111...` без `StringDataRightTruncationError`.

## Проверки (после аудита 23.06.2026)
- `python -m pytest tests/ -q` → **293 passed, 1 deselected (slow)**
- `ruff check src/ tests/` → **All checks passed!**
- `npm run build` во frontend → **не проверен** (требуется `npm install` с доступом к registry)

- [x] **Phase E — partial failure в sync /analyze-multi** (22.06.2026)
  - ✅ `MethodologyFailure` + `MultiAnalysisResponse` модели
  - ✅ При ошибке одной методики успешные сохраняются, ошибки возвращаются отдельно
  - ✅ Санитизация ошибок (≤200 символов, без traceback)
  - ✅ +6 тестов (4 unit + 2 API)
- [x] **Phase C — Embedding DI** (22.06.2026)
  - ✅ `EmbeddingFn` protocol в `src/integrations/embeddings/protocol.py`
  - ✅ `RCARepository.__init__()` принимает `embed_fn` для инъекции
  - ✅ `PersistenceService` создаёт `embed_fn` с автофолбэком на `LocalHashEmbeddingService`
  - ✅ `embed_fn` передаётся во все 7 мест создания `RCARepository`
  - ✅ Убрана прямая зависимость `db` → `services`
- [x] **SSE hardening (Phase D)** (22.06.2026)
  - ✅ Заголовки: `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`
  - ✅ Heartbeat: `{"status":"ping"}` каждые 30 секунд в оба SSE-стрима
  - ✅ Корректная отмена heartbeat-таска при завершении стрима

## Аудит 23.06.2026 — закрытые проблемы из code-quality-audit (hotfix 2)
- [x] **P1 — Ownerless sessions** — `GET /sessions/{session_id}` теперь блокирует доступ для обычных user (аналогично results)
- [x] **P1 — Heartbeat multiplexing** — переписан через `asyncio.wait` с race между `__anext__` и таймером (ping реально уходит во время долгого LLM-вызова)
- [x] **P0 — npm audit** — Vite обновлён с 5.4.21 до 8.0.16 (0 vulnerabilities после `npm audit --audit-level=moderate`)
- [x] **P2 — Chunked upload** — добавлен `_read_limited()` (чтение чанками по 1МБ с проверкой лимита до полной загрузки)
- [x] **P2 — Mypy config** — `strict=true` → `strict=false` + gradual typing (domain/auth overrides)
- [x] **P2 — build artifacts** — удалены `apply-p14.ps1`, `apply-p18-19-8.ps1`, `rewrite-frontend.zip`, корневой `package-lock.json`
- [x] **P2 — package-lock.json** — синхронизирован после установки Vite 8

## Проверки (после hotfix 2)
- `python -m pytest tests/ -q` → **295 passed, 1 deselected (slow)**
- `ruff check src/ tests/` → **All checks passed!**
- `npm run build` во frontend → **✓ built in 777ms**
- `npm audit --audit-level=moderate` → **0 vulnerabilities**

## Известные проблемы (не закрыты)
- [ ] **Mypy** — всё ещё 130+ error (понижен до `strict=false`; требуется постепенная чистка)
- [ ] **save_result status** — доменный Recommendation.status теперь сохраняется (исправлено)
- [ ] **Админ-доступ к ownerless-результатам** — NULL user_id трактуется как admin-only (исправлено)

## В работе / следующий приоритет
- [ ] (Опционально) Прогнать e2e с `EMBEDDINGS_PROVIDER=openrouter` на реальном ключе.

## Аудит качества кода (15.06.2026)
- [x] **Документация аудита** — [code-quality-audit.md](code-quality-audit.md)
- [x] **План рефакторинга SSE/БД** — [refactoring-plan-sse-db.md](refactoring-plan-sse-db.md)
- [x] **P0 — incident_id в runners** (15.06.2026)
- [x] **P0 — SSE multi-analysis** (15.06.2026)
- [x] **P0 — SimilarIncidentsHint.css** (15.06.2026)

## Известные проблемы / нюансы
- `EMBEDDINGS_PROVIDER=huggingface`: первый запрос скачивает модель с HF Hub (~120MB) — в Docker стоит смонтировать volume под `HF_HOME`. Для нейросетевых эмбеддингов дефолтный `threshold=0.15` слишком низкий — используйте 0.55–0.6.
- Смешивать провайдеры безопасно: поиск фильтрует по `model_name`, backfill лениво переиндексирует чужие векторы.
- При `EMBEDDINGS_PROVIDER=openrouter` embeddings становятся платными запросами (≈ $0.02/1M токенов).
- После смены провайдера старые векторы переиндексируются лениво (батчами по 100 при каждом поиске похожих).
- Для production БД требуется `pgvector`; после обновления нужно выполнить `alembic upgrade head`.
