# contracts.md — Контракты данных RCA Analyzer

> **Назначение файла:** Единый источник правды для всех модулей проекта.
> Любой новый чат с AI-ассистентом должен получить этот файл как первый контекст.
> Запрещено менять типы и названия полей без обновления этого документа.
>
> **Дата актуализации:** 2026-06-11 (приоритет E: качество embeddings — local v2 + OpenRouter-провайдер, см. раздел 14.1).

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
api.similarIncidents(text, options) // GET  /api/v1/incidents/similar?text=... → SimilarIncident[]
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

Два провайдера, выбор через env `EMBEDDINGS_PROVIDER` (`local` | `openrouter`):

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

**2. `openrouter`** — `OpenRouterEmbeddingService`
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
EMBEDDINGS_PROVIDER=local|openrouter        # default: local
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

### 14.4. API: `GET /api/v1/incidents/similar`

Защищённый endpoint (auth required). User видит только свои результаты, admin — все.

Query params:

```text
text: str                         # required, min_length=3, max_length=5000
limit: int = 5                    # 1..20
threshold: float = 0.15           # 0..1
exclude_result_id: str | None     # исключить конкретный результат
exclude_incident_id: str | None   # исключить текущий incident_id
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
```

### 14.5. Frontend UI

Компонент `SimilarIncidentsPanel.jsx` показывает карточки похожих случаев:

- процент похожести (`similarity * 100`),
- методику,
- дату,
- summary,
- preview корневых причин и рекомендаций,
- result/incident id.

Точки подключения:

1. `IncidentForm.jsx` — ручной поиск похожих по введённому описанию до запуска анализа.
2. `ResultView.jsx` — автоматический поиск похожих после анализа, с исключением текущего `result_id` и `incident_id`.
