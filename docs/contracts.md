# contracts.md — Контракты данных RCA Analyzer

> **Назначение файла:** Единый источник правды для всех модулей проекта.
> Любой новый чат с AI-ассистентом должен получить этот файл как первый контекст.
> Запрещено менять типы и названия полей без обновления этого документа.
>
> **Дата актуализации:** 2026-06-08 (приоритет C: валидация MultiAnalysisRequest, улучшенный compare(), обработка ошибок, тесты, фикс маршрутизации).

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
api.analyze(payload)       // POST /api/v1/analyze      → RCAResult
api.analyzeMulti(payload)  // POST /api/v1/analyze-multi → RCAResult[]
api.compareResults(id)     // GET  /api/v1/results/compare?incident_id=... → ComparisonResult
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

