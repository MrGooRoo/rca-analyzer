# contracts.md — Контракты данных RCA Analyzer

> **Назначение файла:** Единый источник правды для всех модулей проекта.
> Любой новый чат с AI-ассистентом должен получить этот файл как первый контекст.
> Запрещено менять типы и названия полей без обновления этого документа.
>
> **Дата актуализации:** 2026-06-14 (миграция App.jsx на useAuth + useToast, см. раздел 16; ранее — 13.06.2026, сущность «исследование» analysis_session, разделы 10.5, 15).

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
api.analyze(payload)                // POST /api/v1/analyze      → RCAResult
api.analyzeMulti(payload)           // POST /api/v1/analyze-multi → RCAResult[]
api.compareResults(id)              // GET  /api/v1/results/compare?incident_id=... → ComparisonResult
api.similarIncidents(text, options) // POST /api/v1/incidents/similar (текст в теле) → SimilarIncident[]
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

### 10.4. Состояние App.jsx

- `result` — результат одиночного анализа (`RCAResult | null`)
- `comparison` — результат сравнения (`ComparisonResult | null`)
- Оба сбрасываются при новом анализе
- `!comparison && result` → `ResultView`
- `comparison` → `CompareView`

### 10.5. История анализов: сравнение = одно исследование (добавлено 12.06.2026)

**Семантика:** результаты multi-анализа (N методик по одному инциденту) — это ОДНО
исследование с общими входными данными. Раньше история показывала их как N отдельных
записей; теперь они группируются.

**Группировка (HistoryPage.jsx, функция `groupByIncident`):**

```js
// Вход: плоский список RCAResult из GET /api/v1/results
// Выход: массив групп, отсортированный по дате самого нового результата
{ isCompare: false, result }                 // одиночный анализ
{ isCompare: true,  incidentId, results[] }  // сравнение (>= 2 результатов
                                             // с одним incident_id)
```

**Карточка-группа `CompareGroupCard`:**

- бейдж «⚖️ Сравнение · N методики», тяжесть, дата, summary самого нового результата;
- суммарные показатели: Σ рекомендаций, Σ токенов, средняя уверенность по группе;
- чипы методик (`hcard-method-chip`): клик по чипу → открыть конкретный RCAResult
  (`onOpen`, с `e.stopPropagation()`), клик по карточке → сравнение целиком
  (`api.compareResults(incidentId)` → `onOpenComparison`).

**Фильтры истории работают по группам:**

- поиск/методика/тяжесть: группа подходит, если подходит ХОТЯ БЫ один её результат;
- тип «Одиночные» / «Сравнения» — по `isCompare`.

> ⚠️ Группировка опирается на общий `incident_id` (соглашение: `/analyze-multi`
> присваивает всем результатам один `incident_id`). Запланирован «вариант 2» —
> явная сущность исследования (analysis_session) в БД, см. state.md.

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

Точки подключения:

1. `IncidentForm.jsx` — ручной поиск похожих по введённому описанию до запуска анализа.
2. `ResultView.jsx` — автоматический поиск похожих после анализа, с исключением текущего `result_id` и `incident_id`.

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
- `HistoryPage.jsx`: `groupByIncident()` группирует по `session_id`
  (приоритет) или `incident_id` (fallback для старых данных)
- `CompareGroupCard` передаёт `session_id` в `compareResults()`

### 15.6. Жизненный цикл

1. **POST /analyze** → создаёт сессию → возвращает `session_id` в `RCAResult`
2. **POST /analyze-multi** → создаёт ОДНУ сессию → все N результатов
   получают один `session_id`
3. **POST /analyze-multi-stream** — аналогично: одна сессия на все методики
4. **GET /sessions** — история по исследованиям (вместо плоской списка результатов)
5. **GET /results/compare?session_id=...** — сравнение по сессии

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
