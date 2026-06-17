# contracts.md — Контракты данных RCA Analyzer

> **Назначение файла:** Единый источник правды для всех модулей проекта.
> Любой новый чат с AI-ассистентом должен получить этот файл как первый контекст.
> Запрещено менять типы и названия полей без обновления этого документа.
>
> **Дата актуализации:** 2026-06-17 (зафиксирован план п.17 — LLM Conductor: admin-настройки моделей, порог качества и verifier-схема; см. раздел 17; ранее — SSE-статус одиночного анализа, p16 shared OpenRouter client, UI-kit и analysis_session).

---

## 1. Входные данные — `IncidentInput` + `Victim`

Основная модель, которую принимает `analysis_service` и `upload-report`. Используется в API, frontend-форме (IncidentForm.jsx), тестах и извлечении из DOCX.

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date, time

class Victim(BaseModel):
    """Сведения о пострадавшем (детализировано для отчётов)."""
    full_name: str | None = None
    birth_date: date | None = None
    age: int | None = None
    family_status: str | None = None
    children_under_21: int | None = None
    profession: str | None = None
    workplace: str | None = None
    total_experience: str | None = None
    experience_in_organization: str | None = None
    qualification_certificate: str | None = None
    introductory_briefing: str | None = None
    workplace_briefing: str | None = None
    internship: str | None = None
    safety_knowledge_test: str | None = None
    medical_examination: str | None = None
    diagnosis_severity: str | None = None

    @field_validator('birth_date', mode='before')
    @classmethod
    def parse_birth_date(cls, v):
        """Принимает строку 'YYYY-MM-DD', date или None."""
        if v is None or v == '' or v == 'None':
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            try:
                return date.fromisoformat(v.strip())
            except (ValueError, TypeError):
                return None
        return None

class IncidentInput(BaseModel):
    # --- Основные поля (обязательные в форме) ---
    title: str
    description: str
    incident_date: datetime | None = None
    location: str = ""
    incident_type: str  # e.g. "injury", "equipment", "fire" и т.д.
    severity: str       # "critical" | "major" | "moderate" | "minor" | "near_miss"

    # --- Старые необязательные поля (для обратной совместимости) ---
    victims: Optional[int] = None
    equipment: Optional[str] = None
    conditions: Optional[str] = None
    actions_taken: Optional[str] = None

    # --- Расширенные поля (извлекаются из DOCX-отчётов) ---
    incident_time: time | None = None
    company: str | None = None
    department: str | None = None
    location_detailed: str | None = None
    injured_count: int | None = None
    fatalities_count: int | None = None
    short_description: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
    victims_list: list[Victim] = Field(default_factory=list)
    scene_description: str | None = None
    equipment_description: str | None = None
    full_circumstances: str | None = None
    established_facts: str | None = None
---

## 10. Frontend UI — сравнение методик (добавлено 08.06.2026)

### 10.1. Режимы формы IncidentForm

Форма инцидента (`IncidentForm.jsx`) поддерживает два режима:

- **`mode: 'single'`** — одиночный анализ. Одно поле `methodology` (dropdown).
- **`mode: 'multi'`** — сравнение. Массив `methodologies` (checkboxes, минимум 2).

### 10.2. API-клиент (api.js)

```js
api.analyze(payload, { signal }?)       // POST /api/v1/analyze        → RCAResult (legacy/sync)
api.analyzeStream(payload, onEvent, { signal }?) // POST /api/v1/analyze-stream → SSE/RCAResult
api.analyzeMulti(payload, { signal }?)  // POST /api/v1/analyze-multi  → RCAResult[]
api.analyzeMultiStream(payload, onEvent, { signal }?) // POST /api/v1/analyze-multi-stream → SSE/results
api.compareResults(id)                  // GET  /api/v1/results/compare?incident_id=... → ComparisonResult
api.similarIncidents(text, options)     // POST /api/v1/incidents/similar (текст в теле) → SimilarIncident[]
```

### 10.3. Компонент CompareView

Новый компонент `CompareView.jsx` отображает:

1. **Сводку сравнения** — `comparison.summary`
2. **Общие рекомендации** — `comparison.common_recommendations`
3. **Различающиеся выводы** — `comparison.differing_causes` (сетка карточек по методикам)
4. **Side-by-side табы** — каждая методика как вкладка с детальным результатом:
   - Мета (модель, токены, уверенность)
   - Дерево причин (корневые / способствующие / непосредственные)
   - Bowtie-диаграмма (для bowtie)
   - Рекомендации

### 10.4. Состояние App.jsx и UI-состояния анализа (обновлено 14.06.2026)

- Авторизация в `App.jsx` берётся из `useAuth()` (`user`, `authLoading`, `logout`), а не из локальной bootstrap-логики.
- Ошибки анализа показываются через `useToast()`, без inline `alert-error` в `App.jsx`.
- `result` — результат одиночного анализа (`RCAResult | null`).
- `comparison` — результат сравнения (`ComparisonResult | null`).
- Оба сбрасываются при запуске нового анализа и по кнопке «Новый анализ».
- Страница `analyze` работает как 3-state UI:
  1. **ВВОД**: `!result && !comparison` → показана `IncidentForm`.
  2. **АНАЛИЗ**: `loading=true` → `IncidentForm` получает `loading` и блокирует ввод через `busy = loading || uploading`.
  3. **РЕЗУЛЬТАТ**: `result || comparison` → форма скрыта, показана панель результата и `ResultView`/`CompareView`.
- `!comparison && result` → `ResultView`.
- `comparison` → `CompareView`.
- В режиме просмотра из истории (`page === 'view'`) доступны «Назад в историю» и «Новый анализ».
- Если `loading=true`, внутренние переходы из активного анализа в «Историю», «Пользователи» или «Выйти» сначала показывают `window.confirm` с предупреждением о незавершённом анализе.
- При подтверждённом уходе `App.jsx` отменяет текущий HTTP-запрос через `AbortController` и отвязывает UI от in-flight запроса через `analysisRunRef`: поздний результат одиночного анализа не открывает экран автоматически, а SSE-прогресс multi-analysis размонтируется без вызова `onDone/onError`.
- Во время анализа под формой отображается панель с кнопкой «Отменить анализ». Она вызывает `abortController.abort()`, сбрасывает `loading`, закрывает SSE-прогресс и оставляет пользователя на форме.
- При закрытии/обновлении вкладки во время `loading=true` регистрируется `beforeunload`, чтобы браузер показал системное предупреждение.

### 10.4.1. IncidentForm и UI-kit поля (обновлено 14.06.2026)

- Основные поля `IncidentForm.jsx` используют UI-kit компоненты:
  - `Input` — текстовые, числовые, date/time поля;
  - `Textarea` — описания, фото-ссылки, обстоятельства, установленные факты;
  - `Select` — тип/тяжесть инцидента, методология, детализация.
- Нативные `<input>` оставлены только там, где нужен специальный кастомный UI:
  - скрытый file input для DOCX;
  - radio-переключатель режима анализа;
  - checkbox-карточки методик в multi-режиме.
- Все поля формы и оставшиеся native controls получают `disabled={busy}` при анализе или загрузке DOCX.

### 10.4.2. SSE-прогресс multi-analysis (обновлено 14.06.2026)

- Для режима «Сравнить методики» frontend использует `api.analyzeMultiStream(payload, onEvent, { signal })`, а не обычный `api.analyzeMulti(payload)`.
- `App.jsx` хранит `multiProgressPayload`; пока он задан и `loading=true`, под заблокированной `IncidentForm` отображается `AnalysisProgress`.
- `AnalysisProgress.jsx` запускает `POST /api/v1/analyze-multi-stream` при монтировании и обрабатывает события:
  - `started` → создаёт список методик и сразу помечает все выбранные методики как `running`, потому что backend запускает их параллельно через `asyncio.create_task`;
  - `progress` → отмечает конкретную методику как `done`;
  - `error_one` → отмечает конкретную методику как `error`;
  - `done` → отдаёт `results` в `App.jsx` через `onDone`;
  - `error`/network error → вызывает `onError`.
- После `done` `App.jsx` вызывает `api.compareResults(incidentId, sessionId)` и показывает `CompareView`.
- Форма во время SSE-анализа остаётся на экране, но получает `loading`, поэтому поля заблокированы через `busy = loading || uploading`.

### 10.5. История анализов: сравнение = одно исследование (добавлено 12.06.2026)

**Семантика:** результаты multi-анализа (N методик по одному инциденту) — это ОДНО
исследование с общими входными данными. Раньше история показывала их как N отдельных
записей; теперь они группируются.

**Загрузка истории (HistoryPage.jsx, обновлено 14.06.2026):**

История загружается через `GET /api/v1/sessions`, а не через плоский `GET /results`.
Пагинация (`limit/offset`) теперь идёт по исследованиям (`analysis_sessions`), поэтому
результаты одного сравнения методик не разрываются между страницами.

`HistoryPage.jsx` преобразует `AnalysisSession[]` в элементы отображения функцией
`sessionsToHistoryGroups()`:

```js
// Вход: AnalysisSession[] из GET /api/v1/sessions
// Выход:
{ isCompare: false, result, session }                         // одиночный анализ
{ isCompare: true, sessionId, incidentId, results[], session } // сравнение
```

Для удобства старых UI-компонентов каждый `RCAResult` в истории получает fallback
`incident` из полей сессии (`incident_title`, `incident_severity`, и т.д.).

**Карточка-группа `CompareGroupCard`:**

- бейдж «⚖️ Сравнение · N методики», тяжесть, дата, summary самого нового результата;
- суммарные показатели: Σ рекомендаций, Σ токенов, средняя уверенность по группе;
- чипы методик (`hcard-method-chip`): клик по чипу → открыть конкретный RCAResult
  (`onOpen`, с `e.stopPropagation()`), клик по карточке → сравнение целиком
  (`api.compareResults(incidentId)` → `onOpenComparison`).

**Фильтры истории работают по группам:**

- поиск/методика/тяжесть: группа подходит, если подходит ХОТЯ БЫ один её результат;
- тип «Одиночные» / «Сравнения» — по `isCompare`.

**UI-kit контракт HistoryPage (обновлено 14.06.2026):**

- `HistoryCard` и `CompareGroupCard` используют `Card` из `components/ui/Card.jsx`.
- Фильтры истории используют `Input` и `Select` из `components/ui/Field.jsx`.
- Кнопки обновления, сброса фильтров, пагинации и чипы методик используют `Button`.
- `Card`, `CardHeader`, `CardBody` пробрасывают DOM props (`onClick`, `title`, `role` и др.) через `...rest`, чтобы карточки могли быть интерактивными.

> ⚠️ Группировка уже предпочитает `session_id` и использует `incident_id` только как fallback для старых данных. Следующий этап — загрузка истории напрямую через `/sessions`, чтобы пагинация работала по исследованиям, а не по плоскому списку результатов.

---

## 11. MultiAnalysisRequest — валидация (обновлено 08.06.2026, приоритет C)

```python
class MultiAnalysisRequest(BaseModel):
    methodologies: list[MethodologyType] = Field(..., min_length=2, max_length=5)
    language: str = "ru"
    detail_level: int = Field(default=2, ge=1, le=3)
    incident: IncidentInput

    @field_validator('methodologies')
    @classmethod
    def validate_unique_methodologies(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Методики не должны повторяться')
        return v
```

**Правила:**
- `methodologies`: минимум 2, максимум 5 уникальных методик
- Дубликаты отклоняются с ошибкой валидации (422)
- Диапазон совпадает с методиками из `MethodologyType`

---

## 12. Алгоритм compare() (обновлено 08.06.2026, приоритет C)

`AnalysisService.compare(results)` — нечёткое сравнение результатов нескольких методик:

1. **Общие рекомендации** (`common_recommendations`):
   - Сравнение текстов рекомендаций через `SequenceMatcher` с порогом ≥0.55
   - Рекомендация считается «общей», если встречается в ≥2 методиках
   - Выводится один раз (из первого совпадения)

2. **Различающиеся причины** (`differing_causes`):
   - `dict[str, list[str]]` — ключ = `methodology.value`
   - Причины, уникальные для каждой методики (нет похожих в других)
   - Проверяются все уровни: root + contributing + immediate

3. **Сводка** (`summary`):
   - Автоматически генерируемый текст с числом методик, общих рекомендаций, уникальных причин и средней уверенностью по каждой методике

---

## 13. Маршрутизация — порядок роутов (фикс 08.06.2026)

В `analyze.py` фиксированные пути (`/results`, `/results/compare`) определены **ДО** параметризованного `/results/{result_id}`, чтобы FastAPI не перехватывал `compare` как `result_id`.

---

## 14. Векторный поиск похожих инцидентов / RAG baseline (добавлено 10.06.2026)

### 14.1. Embedding-модель (обновлено 11.06.2026)

Три провайдера, выбор через env `EMBEDDINGS_PROVIDER` (`local` | `huggingface` | `openrouter`):

```python
EMBEDDING_DIMENSION = 384            # фиксированная размерность хранения (pgvector)
EMBEDDING_MODEL_NAME = "local/hash-ngrams-v2"   # локальный baseline
```

**1. `local` (по умолчанию)** — `LocalHashEmbeddingService`, модель `local/hash-ngrams-v2`:

- детерминированный feature hashing без внешних API;
- v2-признаки на токен: `tok:` (слово, 1.0), `stem:` (русский стем, 0.9),
  `concept:` (HSE-концепт из словаря синонимов, 1.6), `tri:`/`quad:` (n-граммы, 0.35/0.20);
- словарь `_CONCEPT_PREFIXES` (~17 концептов: fall, ladder, fire, electricity, gas, ppe…)
  сближает синонимы без общих слов («стремянка» ↔ «лестница», «пожар» ↔ «возгорание»).

**2. `huggingface`** — `HFLocalEmbeddingService`
(`src/integrations/embeddings/hf_local.py`), **рекомендуемый** для production:

- локальная предобученная модель, default `cointegrated/rubert-tiny2`
  (29M параметров, ~120MB, быстрый CPU-инференс, лучший баланс для русского);
- `model_name` в БД: `hf/<model_id>` (например `hf/cointegrated/rubert-tiny2`);
- mean pooling по attention mask → L2-нормализация → паддинг/усечение до 384;
- модели семейства E5 автоматически получают префикс `query: `;
- ленивая потокобезопасная загрузка; инференс в `asyncio.to_thread`;
- требует extras `pip install -e ".[embeddings]"` (torch CPU + transformers);
  без них / без сети при первом скачивании → `EmbeddingServiceError` → фолбэк на local;
- ⚠️ для нейросетевых эмбеддингов рекомендуемый `threshold` поиска похожих —
  **0.55–0.6** (несвязанные тексты дают ~0.4–0.5, а не ~0 как у hashing).

Замеры на HSE-кейсах (cosine similarity, hash-v2 → rubert-tiny2):
синонимы 0.39–0.59 → **0.67–0.73**; перефраз без общих слов 0.14 → **0.71**;
несвязанные 0.00 → 0.37–0.48 (порог различим).

**3. `openrouter`** — `OpenRouterEmbeddingService`
(`src/integrations/llm/openrouter_embeddings.py`):

- POST `https://openrouter.ai/api/v1/embeddings` (OpenAI-совместимый);
- модель из `OPENROUTER_EMBEDDING_MODEL` (default `openai/text-embedding-3-small`);
- запрашивает `dimensions=384` (Matryoshka); если модель не принимает параметр —
  повтор без него + усечение/дополнение вектора до 384 с L2-нормализацией;
- retry с backoff на 408/429/5xx и сетевые ошибки;
- `embed()` — **корутина**; протокол `EmbeddingService.embed` допускает sync и async.

**Контракт хранения и фолбэк:**

- в `result_embeddings.model_name` пишется модель, которая *реально* построила вектор;
- поиск похожих сравнивает только векторы той же модели, что и query
  (`WHERE model_name = query_model`) — пространства разных моделей не смешиваются;
- при ошибке внешнего провайдера (`EmbeddingServiceError`) `RCARepository._embed()`
  автоматически откатывается на `LocalHashEmbeddingService`;
- `backfill_missing_embeddings()` доиндексирует записи без embedding **или**
  с embedding другой модели (миграция при смене провайдера происходит лениво).

Env-переменные:

```text
EMBEDDINGS_PROVIDER=local|huggingface|openrouter   # default: local
HF_EMBEDDING_MODEL=...                      # default: cointegrated/rubert-tiny2
HF_EMBEDDING_MAX_TOKENS=512
OPENROUTER_EMBEDDING_MODEL=...              # default: openai/text-embedding-3-small
OPENROUTER_EMBEDDING_TIMEOUT=30
OPENROUTER_EMBEDDING_MAX_RETRIES=3
```

### 14.2. Таблица `result_embeddings`

Хранилище векторов — PostgreSQL + pgvector.

```python
class ResultEmbeddingORM(Base):
    __tablename__ = "result_embeddings"

    id: str                         # UUID записи embedding
    result_id: str                  # unique FK → rca_results.result_id, cascade delete
    model_name: str                 # например, local/hash-ngrams-v1
    dimension: int                  # 384
    embedding: vector(384)          # pgvector
    source_text: str                # текст, по которому построен embedding
    created_at: datetime
```

Миграция: `alembic/versions/007_add_result_embeddings.py`.
Docker Compose использует образ БД `pgvector/pgvector:pg16`.

### 14.3. Индексация RCA-результатов

При каждом `RCARepository.save_result(result, user_id=...)` дополнительно создаётся запись в `result_embeddings`.
Текст для индексации собирается из:

- `result.methodology`
- `result.summary`
- `root_causes`, `contributing_causes`, `immediate_causes`
- `recommendations`

Для старых записей есть ленивый backfill: `RCARepository.backfill_missing_embeddings(user_id, limit=100)` вызывается перед поиском похожих.

### 14.4. API: `POST /api/v1/incidents/similar` (обновлено 11.06.2026)

Защищённый endpoint (auth required). User видит только свои результаты, admin — все.

**Основной метод — POST** с текстом в теле запроса (фикс HTTP 431: длинные
описания инцидентов не помещались в query string). Старый GET оставлен как
deprecated для обратной совместимости (короткие тексты).

Тело запроса (`SimilarIncidentsRequest`):

```python
class SimilarIncidentsRequest(BaseModel):
    text: str                          # required, min_length=3, max_length=5000
    limit: int = 5                     # 1..20
    threshold: float | None = None     # 0..1; None → подбирается под провайдер
                                       # (0.15 hashing / 0.55 нейросетевые)
    exclude_result_id: str | None = None
    exclude_incident_id: str | None = None
    # Для дедупа повторных анализов из формы: SHA-256 от title+description
    incident_title: str | None = None
    incident_description: str | None = None
```

Response model:

```python
class SimilarIncident(BaseModel):
    result_id: str
    incident_id: str
    methodology: MethodologyType
    created_at: datetime
    summary: str
    similarity: float = Field(ge=0.0, le=1.0)
    confidence_avg: float
    root_causes_preview: list[str] = Field(default_factory=list)
    recommendations_preview: list[str] = Field(default_factory=list)
    user_id: str | None = None
    user_display_name: str | None = None
    user_email: str | None = None
    # Описание инцидента для контекста сравнения (из сессии)
    incident_title: str | None = None
    incident_description: str | None = None
    incident_date: datetime | None = None
    incident_location: str | None = None
```

### 14.5. Frontend UI

Компонент `SimilarIncidentsPanel.jsx` показывает карточки похожих случаев:

- процент похожести (`similarity * 100`),
- методику,
- дату,
- **описание инцидента** (заголовок, описание, дата/место — из сессии,
  выделено визуальным блоком для контекста сравнения),
- summary,
- preview корневых причин и рекомендаций,
- result/incident id.

**UI-kit контракт (обновлено 14.06.2026):**

- кнопки поиска, сброса фильтров и «Открыть →» используют `Button`;
- фильтры по методике и датам используют `Select`/`Input`;
- карточка похожего инцидента использует `Card`;
- метки похожести, методики, даты и автора используют `Badge`;
- `useCallback(load)` зависит от `incidentTitle` и `incidentDescription`, чтобы автопоиск корректно учитывал дедуп по `incident_hash`.

Точки подключения:

1. `IncidentForm.jsx` — лёгкий `SimilarIncidentsHint` по введённому описанию до запуска анализа.
2. `ResultView.jsx` — полный `SimilarIncidentsPanel`: автоматический поиск похожих после анализа, с исключением текущего `result_id`/`incident_id` и дедупом по `incident_hash`.

---

## 15. Сущность «исследование» — analysis_session (добавлено 13.06.2026)

### 15.1. Модель AnalysisSession

Логическая группа анализов одного инцидента. Для одиночного анализа — одна сессия
с одним результатом. Для сравнения методик — одна сессия с N результатами.

```python
class AnalysisSession(BaseModel):
    id:                     str
    created_at:             datetime
    user_id:                str | None              = None
    user_display_name:      str | None              = None
    user_email:             str | None              = None
    incident_title:         str
    incident_description:   str
    incident_date:          datetime | None         = None
    incident_location:      str | None              = None
    incident_type:          str | None              = None
    incident_severity:      str | None              = None
    incident_data_json:     str | None              = None
    results:                list[RCAResult]         = Field(default_factory=list)
```

### 15.2. Таблица `analysis_sessions`

```python
class AnalysisSessionORM(Base):
    __tablename__ = "analysis_sessions"
    id: Mapped[str]                    # UUID
    created_at: Mapped[datetime]
    user_id: Mapped[str | None]        # FK → users.id
    incident_title: Mapped[str]
    incident_description: Mapped[str]
    incident_date: Mapped[datetime | None]
    incident_location: Mapped[str | None]
    incident_type: Mapped[str | None]
    incident_severity: Mapped[str | None]
    incident_data_json: Mapped[str | None]  # полный IncidentInput как JSON
```

Миграция: `alembic/versions/008_add_analysis_sessions.py`.
Backfill: для каждого уникального `incident_id` в `rca_results` создаётся
одна сессия, и все результаты с этим `incident_id` получают `session_id`.

### 15.3. Связь RCAResult → AnalysisSession

`RCAResult.session_id` (str | None, nullable) — FK → `analysis_sessions.id`.
Поле `incident_id` остаётся для обратной совместимости.

### 15.4. API-эндпоинты

```python
# Новые эндпоинты
GET /api/v1/sessions?limit=20&offset=0          → list[AnalysisSession]
GET /api/v1/sessions/{session_id}               → AnalysisSession (с результатами)

# Обновлённые эндпоинты
GET /api/v1/results/compare?session_id=...      → ComparisonResult  # новый параметр
GET /api/v1/results/compare?incident_id=...     → ComparisonResult  # backward compat
```

Правило: если указан `session_id`, используется он (результаты читаются
по `session_id` из БД). Если указан только `incident_id` — fallback
для обратной совместимости.

### 15.5. Фронтенд

- `api.sessions.list(limit, offset)` — список сессий
- `api.sessions.get(sessionId)` — получить сессию
- `api.compareResults(incidentId, sessionId)` — предпочитает `session_id`
- `HistoryPage.jsx`: загружает `api.sessions.list()` и отображает историю по `AnalysisSession`, а не по плоскому списку результатов
- `sessionsToHistoryGroups()` преобразует сессии в одиночные карточки или группы сравнения; fallback `incident` для карточек формируется из полей сессии
- `CompareGroupCard` передаёт `session_id` в `compareResults()`

### 15.6. Жизненный цикл

1. **POST /analyze** → создаёт сессию → возвращает `session_id` в `RCAResult` (legacy/sync)
2. **POST /analyze-stream** → SSE-статус → сохраняет результат и сессию → финальное событие `done` с `RCAResult`
3. **POST /analyze-multi** → создаёт ОДНУ сессию → все N результатов получают один `session_id`
4. **POST /analyze-multi-stream** — аналогично: одна сессия на все методики
5. **GET /sessions** — история по исследованиям (вместо плоской списка результатов)
6. **GET /results/compare?session_id=...** — сравнение по сессии

---

## 16. Frontend: AuthContext + Toast + UI-kit (добавлено 14.06.2026)

### 16.1. Глобальные провайдеры (`main.jsx`)

Приложение обёрнуто в два провайдера:

```jsx
<AuthProvider>      // контекст авторизации (login/register/logout/refresh)
  <ToastProvider>   // всплывающие уведомления (info/success/error/warning)
    <App />
  </ToastProvider>
</AuthProvider>
```

Любой компонент может вызвать `useAuth()` или `useToast()` без проброса пропсов.

### 16.2. AuthContext — контракт

```ts
const { user, loading, login, register, logout, refresh } = useAuth()
```

- `user: User | null` — текущий пользователь (`{id, email, display_name, role}`)
  или `null`, если не залогинен.
- `loading: boolean` — `true` пока выполняется начальный `api.auth.me()`.
  Используется для экрана «Проверка сессии…».
- `login(email, password)` / `register(email, name, password)` — мутируют `user`.
- `logout()` — дёргает `api.auth.logout()`, ставит `user = null`.
- `refresh()` — ручной рефреш (например, после смены роли админом).

**Реакция на потерю сессии (любой 401):**

`AuthProvider` в `useEffect` регистрирует глобальный обработчик
`setAuthLostHandler` из `api.js`. Если любой запрос (analyze, compareResults,
uploadReport и т.д.) возвращает 401 и refresh не помог —
`AuthProvider` ставит `user = null`.

`App.jsx` через `useEffect` следит за `user`:
при переходе `user → null` сбрасывает транзиентное состояние
(`result`, `comparison`, `viewMode`, `page`) — пользователь возвращается на
`AuthPage` с чистым состоянием.

### 16.3. Toast — контракт

```ts
const toast = useToast()
toast.success(message, title?)
toast.error(message, title?)
toast.info(message, title?)
toast.warning(message, title?)
toast.push({ message, title?, tone: 'success' | 'error' | 'info' | 'warning' })
```

Тосты автоматически закрываются через 5 секунд. Позиция: фиксированная,
top-right, `z-index: 9999`. Контейнер — `.toast-container` в `Toast.css`.

### 16.4. UI-kit компоненты (`frontend/src/components/ui/`)

| Компонент | Импорт | Назначение |
|---|---|---|
| `Button` | `./ui/Button.jsx` | Кнопки с `variant` (`primary`/`secondary`/`ghost`/`danger`/`outline`), `size` (`sm`/`md`/`lg`), `loading` (спиннер) |
| `Card` + `CardHeader` + `CardBody` | `./ui/Card.jsx` | Контейнеры карточек |
| `Badge` | `./ui/Card.jsx` | Тонированные метки (`slate`/`indigo`/`emerald`/`amber`/`rose`/`sky`/`violet`) |
| `Input` + `Textarea` + `Select` + `FieldWrapper` | `./ui/Field.jsx` | Поля ввода с `label`/`hint`/`error` |
| `ToastProvider` + `useToast` | `./ui/Toast.jsx` | Уведомления |
| `AuthProvider` + `useAuth` | `./context/AuthContext.jsx` | Авторизация |
| `methodologyMeta(id)` | `./lib/methodologies.js` | Метаданные методологии (иконка, цвет, описание) |
| `cn(...classes)` | `./utils/cn.js` | clsx + tailwind-merge |

### 16.5. App.jsx — обновлённое состояние (14.06.2026)

До миграции App.jsx сам управлял `sessionReady`, `user`, дублировал auth-логику
и показывал ошибки через `<div className="alert alert-error">`. После:

- `user` и `authLoading` берутся из `useAuth()`.
- Ошибки анализа уходят в `toast.error(message, 'Ошибка')` — больше нет
  локального state `error` и нет красного блока.
- Транзиентное состояние (`result`, `comparison`, `viewMode`, `page`)
  сбрасывается через `useEffect` при `user → null`.
- Навигация и кнопка «Выйти» используют `<Button>` из UI-kit.
- `AuthPage.jsx` больше НЕ принимает `onAuth` prop — сам вызывает
  `useAuth().login/register`.


---

## 17. P17 LLM Conductor — контракты и план реализации (зафиксировано 17.06.2026)

> Статус раздела: **P17 реализован**. Этапы 1–7 реализованы 17.06.2026: settings, OpenRouter catalog proxy, Admin UI, verifier prompt, `LLMConductor`, интеграция в `AnalysisService` и расширенный audit/provenance моделей/токенов.

### 17.1. Назначение

P17 реализует не простой fallback моделей, а дирижирование:

1. `draft_model` выполняет основной RCA-анализ и формирует черновой `RCAResult`.
2. Если схема требует верификации, `verifier_model` получает инцидент + методологию + JSON-черновик и возвращает улучшенный результат того же формата.
3. Основной экономичный режим: verifier вызывается только если `draft_result.confidence_avg < quality_threshold`.

### 17.2. Таблица `llm_settings` (implemented: migration `011_add_llm_settings.py`)

Singleton-таблица с одной строкой `id=1`.

```python
class LLMSettingsORM(Base):
    __tablename__ = "llm_settings"

    id: int                         # always 1
    draft_model: str                # OpenRouter model id, required
    verifier_model: str | None      # OpenRouter model id; None disables paid verification path
    quality_threshold: float        # 0.0..1.0, default 0.70
    verification_scheme: str        # "disabled" | "threshold" | "always"
    updated_at: datetime
    updated_by: str | None          # email/user id admin-а, изменившего настройки
```

Правила валидации:

- `quality_threshold`: `ge=0.0`, `le=1.0`.
- `verification_scheme`: только `disabled`, `threshold`, `always`.
- `draft_model`: обязательный OpenRouter model id.
- `verifier_model`: обязателен, если `verification_scheme` не `disabled`.
- model id: строка до 200 символов, без пробелов/управляющих символов; допустимые символы slug — `A-Za-z0-9._~:/-`.

### 17.3. Pydantic-схемы (implemented for settings; catalog model prepared)

```python
class LLMSettings(BaseModel):
    draft_model: str
    verifier_model: str | None = None
    quality_threshold: float = Field(0.70, ge=0.0, le=1.0)
    verification_scheme: Literal["disabled", "threshold", "always"] = "threshold"
    updated_at: datetime | None = None
    updated_by: str | None = None

class LLMSettingsUpdate(BaseModel):
    draft_model: str
    verifier_model: str | None = None
    quality_threshold: float = Field(0.70, ge=0.0, le=1.0)
    verification_scheme: Literal["disabled", "threshold", "always"] = "threshold"

class OpenRouterModelInfo(BaseModel):
    id: str
    name: str | None = None
    context_length: int | None = None
    prompt_price_per_1m: float | None = None
    completion_price_per_1m: float | None = None
    is_free: bool = False
```

### 17.4. Admin API

```text
GET /api/v1/admin/llm-settings                         # implemented
PUT /api/v1/admin/llm-settings                         # implemented
GET /api/v1/admin/openrouter/models?search=&free_only=&limit=100  # implemented
```

Требования:

- все endpoints доступны только `role='admin'` через `require_admin(current_user)`;
- CSRF/auth работают так же, как для существующих admin endpoints;
- backend не отдаёт `OPENROUTER_API_KEY` во frontend;
- `/openrouter/models` вызывает публичный каталог OpenRouter server-side, кэширует результат in-memory и возвращает UI-safe `OpenRouterModelInfo[]`.

### 17.5. Frontend API (implemented)

```js
api.admin.getLlmSettings()                 // GET /api/v1/admin/llm-settings
api.admin.updateLlmSettings(payload)        // PUT /api/v1/admin/llm-settings
api.admin.openRouterModels(params)          // GET /api/v1/admin/openrouter/models
```


### 17.6. AdminPage UI (implemented)

`frontend/src/components/AdminPage.jsx` содержит блок **LLM Conductor**:

- загрузка текущих настроек через `api.admin.getLlmSettings()`;
- сохранение через `api.admin.updateLlmSettings(payload)`;
- поиск моделей через `api.admin.openRouterModels({ search, free_only, limit, force_refresh })`;
- поля `draft_model`, `verifier_model`, `verification_scheme`, `quality_threshold`;
- `datalist`/ручной fallback для model id, если каталог OpenRouter недоступен;
- frontend-проверка: при `verification_scheme != "disabled"` verifier-модель обязательна.

### 17.7. Схемы верификации

| `verification_scheme` | Поведение |
|---|---|
| `disabled` | Только `draft_model`, verifier не вызывается |
| `threshold` | Verifier вызывается, если `confidence_avg < quality_threshold` |
| `always` | Verifier вызывается после каждого черновика |


### 17.8. Verifier prompt (implemented)

`configs/prompts/verifier.j2` — Jinja2-шаблон для дешёвой verifier-модели.

Входные переменные:

```jinja2
{{ incident }}
{{ methodology }}
{{ draft_result_json }}
{{ low_confidence_nodes }}
{{ output_schema_hint }}
```

Контракт:

- verifier не выполняет полный анализ с нуля, а проверяет и точечно улучшает черновой RCA JSON;
- ответ — только валидный JSON без Markdown/code fence;
- верхнеуровневые ключи остаются совместимыми с существующими methodology runners:
  `immediate_causes`, `contributing_causes`, `root_causes`, `summary`, `recommendations`;
- `cause_id` и `parent_id` должны ссылаться на существующие id итогового JSON;
- `confidence` остаётся числом `0.0..1.0`.

`PromptRenderer.render()` поддерживает `extra_context`, чтобы `LLMConductor` мог передать verifier-переменные без отдельного renderer.

### 17.9. Контракт `LLMConductor` (implemented standalone; integration planned)

```python
class LLMConductor:
    def __init__(self, settings: LLMSettings, *, llm_factory=OpenRouterClient, prompt_renderer=None): ...
    async def analyze(self, request: AnalysisRequest, runner: MethodologyRunner) -> RCAResult: ...
```

Логика реализованного standalone-сервиса (`src/services/llm_conductor.py`):

```text
render methodology prompt
→ OpenRouterClient(model=draft_model) → draft raw
→ runner.run(request, draft raw) → draft RCAResult
→ should_verify(settings, draft_result)?
    no  → return draft_result
    yes → render verifier.j2 with IncidentInput + methodology + draft JSON + low-confidence nodes
          → OpenRouterClient(model=verifier_model) → verified raw
          → runner.run(request, verified raw) → final RCAResult
          → model_used = "draft_model -> verifier_model", tokens_used = draft + verifier
```

Интеграция выполнена: `AnalysisService.analyze(..., llm_settings=...)`, `analyze_stream(..., llm_settings=...)` и `analyze_multi(..., llm_settings=...)` используют `LLMConductor`, если настройки переданы из API-роутера. Без настроек сохраняется legacy pipeline.

Верификатор возвращает тот же JSON-контракт, что и обычная методология, чтобы не плодить отдельные result types.

### 17.10. Аудит моделей и токенов (implemented: migration `012_add_llm_provenance.py`)

`RCAResult` и таблица `rca_results` содержат расширенные поля provenance:

```python
draft_model_used: str | None
verifier_model_used: str | None
draft_tokens_used: int | None
verifier_tokens_used: int | None
verification_applied: bool
verification_reason: str | None
```

Правила заполнения:

- если verifier не применялся: `verification_applied=False`, заполнены `draft_model_used` и `draft_tokens_used`, verifier-поля `None`;
- если verifier применялся: `verification_applied=True`, заполнены draft/verifier модели и токены;
- `model_used` остаётся совместимым summary-полем: `draft_model` или `draft_model -> verifier_model`;
- `tokens_used` остаётся суммарным: `draft_tokens + verifier_tokens`.

---


### 17.11. Интеграция в AnalysisService (implemented)

API-роутер анализа загружает admin-настройки из `llm_settings` через `LLMSettingsRepository` и передаёт их в сервис:

- `POST /api/v1/analyze` → `_service.analyze(request, llm_settings=settings)`;
- `POST /api/v1/analyze-stream` → `_service.analyze_stream(request, llm_settings=settings)`;
- `POST /api/v1/analyze-multi` → `_service.analyze_multi(request, llm_settings=settings)`;
- `POST /api/v1/analyze-multi-stream` → каждый `run_one()` вызывает `_service.analyze(single, llm_settings=settings)`.

Контракт совместимости:

- если `llm_settings` не удалось загрузить, API логирует warning и использует legacy pipeline;
- существующие тесты с mock DB не пытаются строить настройки из `AsyncMock`;
- SSE-контракт не ломается: сохраняются стадии `started → preparing → llm → parsing → done/error`, при этом стадия `llm` может включать draft+verifier.

### 17.12. DB compatibility for LLM-generated ids (implemented: migration `013_expand_llm_generated_ids.py`)

LLM may generate ids with semantic prefixes (`imm-<uuid>`, `contrib-<uuid>`, `root-<uuid>`, `r111...`).
To avoid `StringDataRightTruncationError`, persistence columns are wider than pure UUID length:

- `causal_nodes.node_id`: `VARCHAR(200)`;
- `causal_nodes.parent_id`: `VARCHAR(200)`;
- `recommendations.rec_id`: `VARCHAR(200)`;
- `recommendations.cause_id`: `VARCHAR(200)`.

Primary keys (`causal_nodes.id`, `recommendations.id`) and `result_id` remain UUID-length internal identifiers.
