# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении.

## Статус: 🟢 Рабочая версия — analysis_session + embeddings + Apple-style + UI-kit form

**Дата обновления:** 2026-06-14

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
  - ✅ Причина бага: длинный текст инцидента в query string → HTTP 431 Request Header Fields Too Large
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
- [x] **UI-kit + Tailwind + Toast + AuthContext** (13.06.2026)
  - ✅ Tailwind CSS v4: @tailwindcss/vite плагин, только utilities (без reset — не ломает существующие стили)
  - ✅ cn() утилита: clsx + tailwind-merge для корректного слияния классов
  - ✅ Button: варианты primary/secondary/ghost/danger/outline, размеры sm/md/lg, loading-спиннер
  - ✅ Card + CardBody + CardHeader + Badge: тонированные бейджи (7 цветов)
  - ✅ Field: Input, Textarea, Select с label/hint/error
  - ✅ Toast + ToastProvider + useToast: уведомления info/success/error/warning с автозакрытием
  - ✅ methodologies.js: метаданные методологий (иконки, описания, цвета)
  - ✅ AuthContext: чистая архитектура авторизации (login/register/logout/refresh)
  - ✅ main.jsx: обёрнуто в AuthProvider + ToastProvider
- [x] **App.jsx мигрирован на UI-kit** (14.06.2026)
  - ✅ `useAuth()` из AuthContext: убрана дублирующая auth-логика
    (bootstrapSession, sessionReady, setAuth, clearAuth, setAuthLostHandler)
  - ✅ `useToast()` вместо `<div className="alert alert-error">` — ошибки анализа всплывающим тостом
  - ✅ Навигационные кнопки (Анализ / История / Пользователи) → `<Button variant="ghost">`
    с классом `.app-nav-btn--active` для активной страницы
  - ✅ Кнопка «Выйти» → `<Button variant="secondary" size="sm">`
  - ✅ Кнопка «← Назад в историю» → `<Button variant="secondary" size="sm">`
  - ✅ `AuthContext` теперь регистрирует `setAuthLostHandler` — при любом 401
    (не только bootstrap) user сбрасывается в null, и `useEffect` в App.jsx
    чистит транзиентное состояние (result, comparison, viewMode, page)
  - ✅ `AuthPage.jsx`: убран проп `onAuth`, теперь напрямую `useAuth().login/register`
  - ✅ `App.css` почищен: удалены `.nav-btn`, `.nav-btn--active`, `.btn-logout`,
    `.btn-back`, `.alert-error` (заменены Button-вариантами и toast)
- [x] **P2/P6 — явные UI-состояния анализа** (14.06.2026)
  - ✅ Страница анализа разделена на состояния: ВВОД → АНАЛИЗ → РЕЗУЛЬТАТ
  - ✅ После одиночного результата или сравнения `IncidentForm` скрывается, чтобы ввод не смешивался с результатом
  - ✅ Над `ResultView`/`CompareView` добавлена панель результата с кнопкой «➕ Новый анализ»
  - ✅ В просмотре результата из истории теперь есть две кнопки: «Назад в историю» и «Новый анализ»
- [x] **IncidentForm.jsx — поля на UI-kit** (14.06.2026)
  - ✅ Основные поля формы переведены на `Input`, `Textarea`, `Select` из `components/ui/Field.jsx`
  - ✅ Нативные input оставлены только для file/radio/checkbox контролов со специальным UI
  - ✅ Добита блокировка `disabled={busy}` на ранее пропущенных полях: фото-ссылки, семейное положение, инструктажи, стажировка, проверка знаний, медосмотр
  - ✅ Счётчики по коду: `<Input>` 26, `<Textarea>` 6, `<Select>` 5; старые `<textarea>/<select>` отсутствуют
- [x] **HistoryPage.jsx — UI-kit миграция** (14.06.2026)
  - ✅ Карточки одиночных результатов и групп сравнения используют `Card` из UI-kit
  - ✅ Фильтры истории используют `Input` и `Select` из UI-kit
  - ✅ Кнопки обновления, сброса фильтров, пагинации и чипы методик используют `Button`
  - ✅ `Card`/`CardHeader`/`CardBody` теперь пробрасывают DOM props (`onClick`, `title` и др.), чтобы UI-kit карточки можно было использовать интерактивно
  - ✅ Счётчики по коду `HistoryPage.jsx`: `<Card>` 2, `<Button>` 5, `<Input>` 1, `<Select>` 3; нативные `<button>/<input>/<select>` отсутствуют
- [x] **HistoryPage.jsx — загрузка через `/sessions` API** (14.06.2026)
  - ✅ История загружается через `api.sessions.list(PAGE_SIZE, offset)` вместо `api.results.list(...)`
  - ✅ Пагинация теперь идёт по исследованиям (`analysis_sessions`), а не по плоскому списку RCAResult
  - ✅ Сравнение методик не разрывается между страницами истории
  - ✅ `sessionsToHistoryGroups()` преобразует `AnalysisSession[]` в одиночные карточки или группы сравнения
  - ✅ Для карточек формируется fallback `incident` из данных сессии (`incident_title`, `incident_severity`, и т.д.)
  - ✅ `RCARepository.list_sessions()` eager-load'ит user, causal_nodes и recommendations результатов, чтобы `/sessions` отдавал полноценные RCAResult для истории

- [x] **SimilarIncidentsPanel.jsx — UI-kit миграция** (14.06.2026)
  - ✅ Кнопки поиска/сброса фильтров и «Открыть →» используют `Button`
  - ✅ Фильтры по методике и датам используют `Select`/`Input`
  - ✅ Карточка похожего инцидента использует `Card`, метки похожести/методики/даты/автора — `Badge`
  - ✅ Исправлены зависимости `useCallback(load)`: `incidentTitle` и `incidentDescription` участвуют в автопоиске/дедупе
  - ✅ Счётчики по коду: `<Button>` 4, `<Input>` 2, `<Select>` 1, `<Card>` 1, `<Badge>` 4; нативные `<button>/<input>/<select>` отсутствуют

## Проверки
- `python -m pytest tests/ -q` → **257 passed, 1 deselected (slow)**
- `pytest -m slow -o addopts=""` (реальная rubert-tiny2) → **1 passed**
- `ruff check` по изменённым файлам → **All checks passed!**
- `npm run build` во frontend → **успешно**

- [x] **AnalysisProgress.jsx — SSE-прогресс multi-analysis** (14.06.2026)
  - ✅ `App.jsx` подключает `AnalysisProgress` при запуске режима «Сравнить методики»
  - ✅ Multi-analysis теперь идёт через `api.analyzeMultiStream()` / `POST /api/v1/analyze-multi-stream`
  - ✅ Во время сравнения форма остаётся видимой, но заблокированной через `loading`/`busy`, а под ней отображается прогресс по методикам
  - ✅ После SSE `done` результаты передаются в `compareResults(incidentId, sessionId)` и открывается `CompareView`
  - ✅ `AnalysisProgress` переведён на Apple-style dark UI с `Card`/`Badge`, прогресс-баром и состояниями running/done/error
  - ✅ Прогресс отражает параллельный запуск: после события `started` все выбранные методики сразу получают статус «в работе», а затем независимо переходят в «готово» или «ошибка»

- [x] **P3 — предупреждение при уходе во время анализа** (14.06.2026)
  - ✅ При попытке перейти из активного анализа в «Историю», «Пользователи» или выйти из аккаунта показывается `window.confirm`.
  - ✅ При подтверждённом уходе UI отвязывается от текущего in-flight запроса: поздний одиночный результат не перекидывает пользователя обратно на анализ.
  - ✅ Для multi-analysis прогресс размонтируется и больше не вызывает `onDone/onError` после ухода со страницы.
  - ✅ При закрытии или обновлении вкладки во время анализа браузер показывает системное `beforeunload`-предупреждение.

- [x] **P4 — отмена анализа через AbortController** (14.06.2026)
  - ✅ `api.req()` принимает `signal` и прокидывает его в `fetch`.
  - ✅ `api.analyze(payload, { signal })`, `api.analyzeMulti(payload, { signal })` и `api.analyzeMultiStream(payload, onEvent, { signal })` поддерживают отмену.
  - ✅ `App.jsx` создаёт `AbortController` для одиночного и SSE multi-analysis.
  - ✅ Под формой во время анализа показывается панель «Анализ выполняется» с кнопкой «⏹ Отменить анализ».
  - ✅ При отмене сбрасываются `loading`, `multiProgressPayload`, `analysisSignal`; `AbortError` не показывается как ошибка анализа.
  - ✅ При подтверждённом уходе со страницы активный HTTP-запрос также отменяется.
  - ⚠️ Нюанс: если backend уже начал внешний LLM-запрос, браузерная отмена закрывает клиентский запрос, но фактическая остановка на стороне провайдера может быть не мгновенной.

- [x] **Техдолг — httpx deprecation warnings в CSRF-тестах** (14.06.2026)
  - ✅ `tests/api/test_csrf.py`: тестовый клиент создаётся через явный `ASGITransport`, cookie добавляются в jar после создания клиента.
  - ✅ `tests/api/test_csrf_e2e.py`: добавлен общий `_client()` через явный `ASGITransport`, повторяющиеся `AsyncClient(...)` заменены на helper.
  - ✅ CSRF-тесты больше не используют deprecated httpx shortcuts и проверяются с `-W error::DeprecationWarning`.

- [x] **Документация — закрыты TODO-заглушки** (14.06.2026)
  - ✅ `docs/architecture.md`: описаны слои, request flow одиночного и multi-analysis, sessions, embeddings, frontend architecture и правила расширения.
  - ✅ `docs/conventions.md`: зафиксированы соглашения по стеку, неймингу, backend/frontend, auth/CSRF, sessions, embeddings, документации и проверкам.
  - ✅ `docs/methodologies.md`: описаны 5 готовых RCA-методик, runner contract, применимость, multi-analysis и добавление новой методики.

## В работе / следующий приоритет
- [ ] (Опционально) Прогнать e2e с `EMBEDDINGS_PROVIDER=openrouter` на реальном ключе.

## Известные проблемы / нюансы
- `EMBEDDINGS_PROVIDER=huggingface`: первый запрос скачивает модель с HF Hub (~120MB) — в Docker стоит смонтировать volume под `HF_HOME`, чтобы кэш переживал пересборку. Для нейросетевых эмбеддингов дефолтный `threshold=0.15` слишком низкий — используйте 0.55–0.6.
- Смешивать провайдеры безопасно: поиск фильтрует по `model_name`, backfill лениво переиндексирует чужие векторы.
- При `EMBEDDINGS_PROVIDER=openrouter` embeddings становятся платными запросами (text-embedding-3-small ≈ $0.02/1M токенов); при недоступности API всё автоматически работает через local v2.
- После смены провайдера старые векторы переиндексируются лениво (батчами по 100 при каждом поиске похожих); до полной переиндексации часть старых результатов не попадает в выдачу.
- Для production БД требуется `pgvector`: Docker Compose уже переведён на `pgvector/pgvector:pg16`, миграция создаёт `CREATE EXTENSION IF NOT EXISTS vector`.
- На существующей БД после обновления нужно выполнить `alembic upgrade head`.
