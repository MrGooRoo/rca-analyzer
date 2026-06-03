# contracts.md — Контракты данных RCA Analyzer

> **Назначение файла:** Единый источник правды для всех модулей проекта.
> Любой новый чат с AI-ассистентом должен получить этот файл как первый контекст.
> Запрещено менять типы и названия полей без обновления этого документа.

---

## 1. Входные данные — `IncidentInput`

Основная модель, которую принимает `analysis_service`. Используется в API, frontend-форме и тестах.

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

class SeverityLevel(str, Enum):
    CRITICAL   = "critical"    # Смерть / разрушение оборудования
    MAJOR      = "major"       # Тяжёлая травма / значительный ущерб
    MODERATE   = "moderate"    # Лёгкая травма / умеренный ущерб
    MINOR      = "minor"       # Без травм, незначительный ущерб
    NEAR_MISS  = "near_miss"   # Предпосылка к происшествию

class IncidentType(str, Enum):
    INJURY         = "injury"           # Травма персонала
    EQUIPMENT      = "equipment"        # Отказ оборудования
    FIRE           = "fire"             # Пожар / возгорание
    SPILL          = "spill"            # Разлив / утечка
    NEAR_MISS      = "near_miss"        # Предпосылка
    PROCESS_UPSET  = "process_upset"    # Нарушение технологического процесса
    SECURITY       = "security"         # Нарушение безопасности
    ENVIRONMENTAL  = "environmental"    # Экологический инцидент

class IncidentInput(BaseModel):
    # Обязательные поля
    title:          str             = Field(..., min_length=5, max_length=200,
                                        description="Краткое название инцидента")
    description:    str             = Field(..., min_length=20,
                                        description="Подробное описание произошедшего")
    incident_date:  datetime        = Field(..., description="Дата и время инцидента")
    location:       str             = Field(..., description="Объект / цех / участок")
    incident_type:  IncidentType
    severity:       SeverityLevel

    # Необязательные поля
    victims:        Optional[int]   = Field(None, ge=0, description="Число пострадавших")
    equipment:      Optional[str]   = Field(None, description="Задействованное оборудование")
    conditions:     Optional[str]   = Field(None, description="Условия на момент инцидента")
    actions_taken:  Optional[str]   = Field(None, description="Принятые меры по факту")
    witnesses:      Optional[List[str]] = Field(default_factory=list,
                                        description="Показания свидетелей (список)")
    photos:         Optional[List[str]] = Field(default_factory=list,
                                        description="URL фотографий с места")
    attachments:    Optional[List[str]] = Field(default_factory=list,
                                        description="Прочие вложения")
```

---

## 2. Параметры анализа — `AnalysisRequest`

Передаётся из API в `analysis_service` вместе с `IncidentInput`.

```python
class MethodologyType(str, Enum):
    RCA_SYSTEMIC = "rca_systemic"   # Системный RCA (основной)
    FIVE_WHY     = "five_why"       # 5 Почему
    ISHIKAWA     = "ishikawa"       # Диаграмма Исикавы (Рыбья кость)
    FTA          = "fta"            # Fault Tree Analysis (Дерево отказов)
    BOWTIE       = "bowtie"         # Галстук-бабочка (планируется)

class AnalysisRequest(BaseModel):
    incident:     IncidentInput
    methodology:  MethodologyType   = MethodologyType.RCA_SYSTEMIC
    language:     str               = "ru"    # Язык отчёта: "ru" | "en"
    detail_level: int               = Field(2, ge=1, le=3,
                                        description="1=кратко, 2=стандарт, 3=подробно")
    user_id:      Optional[str]     = None
```

---

## 3. Выходные данные — `RCAResult`

Возвращается из `analysis_service`, сохраняется в БД, используется для экспорта.

```python
class CauseNode(BaseModel):
    id:           str               # UUID узла
    text:         str               # Формулировка причины
    category:     str               # Категория (человек / процесс / оборудование / среда)
    level:        int               # Уровень в дереве (0=прямая, 1=промежуточная, 2+=корневая)
    parent_id:    Optional[str]     # ID родительского узла (None для корня)
    confidence:   float             = Field(..., ge=0.0, le=1.0,
                                        description="Уверенность модели 0.0–1.0")

class Recommendation(BaseModel):
    id:           str               # UUID рекомендации
    text:         str               # Описание корректирующего мероприятия
    priority:     str               # "high" | "medium" | "low"
    category:     str               # "immediate" | "short_term" | "systemic"
    cause_id:     str               # Ссылка на CauseNode.id
    responsible:  Optional[str]     # Ответственная роль / подразделение

class RCAResult(BaseModel):
    result_id:      str             # UUID результата
    incident_id:    str             # Ссылка на инцидент в БД
    methodology:    MethodologyType
    created_at:     datetime

    # Основные результаты
    immediate_causes:   List[CauseNode]     # Непосредственные причины
    contributing_causes: List[CauseNode]   # Способствующие факторы
    root_causes:        List[CauseNode]     # Корневые причины
    causal_tree:        List[CauseNode]     # Полное дерево (все узлы)

    # Выводы и рекомендации
    summary:            str                 # Резюме анализа (1–2 абзаца)
    recommendations:    List[Recommendation]

    # Метаданные качества
    model_used:     str                     # Название LLM (e.g. "openai/gpt-4o")
    tokens_used:    int
    confidence_avg: float                   # Средняя уверенность по всем узлам
```

---

## 4. Схема базы данных (PostgreSQL)

```sql
-- Инциденты
CREATE TABLE incidents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL,
    incident_date TIMESTAMPTZ NOT NULL,
    location      TEXT NOT NULL,
    incident_type TEXT NOT NULL,
    severity      TEXT NOT NULL,
    raw_input     JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- Результаты анализа
CREATE TABLE rca_results (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id   UUID REFERENCES incidents(id),
    methodology   TEXT NOT NULL,
    result_data   JSONB NOT NULL,
    model_used    TEXT,
    tokens_used   INT,
    confidence_avg FLOAT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- Векторные эмбеддинги для поиска похожих случаев (pgvector)
CREATE TABLE incident_embeddings (
    incident_id   UUID REFERENCES incidents(id),
    embedding     vector(1536),
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON incident_embeddings USING ivfflat (embedding vector_cosine_ops);
```

---

## 5. API-контракты (REST)

| Метод | URL | Вход | Выход | Описание |
|-------|-----|------|-------|----------|
| `POST` | `/api/v1/incidents` | `IncidentInput` | `{incident_id: str}` | Создать инцидент |
| `POST` | `/api/v1/analysis` | `AnalysisRequest` | `RCAResult` | Запустить анализ |
| `GET`  | `/api/v1/results/{result_id}` | — | `RCAResult` | Получить результат |
| `GET`  | `/api/v1/incidents/{incident_id}/results` | — | `List[RCAResult]` | Все анализы по инциденту |
| `POST` | `/api/v1/results/{result_id}/export` | `{format: "pdf"\|"excel"}` | `{url: str}` | Экспортировать отчёт |
| `GET`  | `/api/v1/incidents/similar` | `?incident_id=&top_k=5` | `List[{incident_id, score}]` | Похожие случаи (pgvector) |

---

## 6. Формат промпт-контракта (LLM → домен)

LLM **обязана** возвращать JSON строго этой формы. Парсер валидирует через Pydantic.

```json
{
  "immediate_causes": [
    {
      "id": "uuid-string",
      "text": "Описание причины",
      "category": "человек | процесс | оборудование | среда | управление",
      "level": 0,
      "parent_id": null,
      "confidence": 0.92
    }
  ],
  "contributing_causes": [...],
  "root_causes": [...],
  "summary": "Текст резюме",
  "recommendations": [
    {
      "id": "uuid-string",
      "text": "Описание мероприятия",
      "priority": "high | medium | low",
      "category": "immediate | short_term | systemic",
      "cause_id": "uuid ссылка на CauseNode",
      "responsible": "Мастер участка / ОТ / ГИП"
    }
  ]
}
```

> **Важно:** Если LLM вернула невалидный JSON — `analysis_service` выбрасывает
> `LLMResponseValidationError` и делает повторный запрос (до 2 retry).

---

## 7. Коды ошибок API

| Код | Константа | Описание |
|-----|-----------|----------|
| `INC_001` | `INCIDENT_NOT_FOUND` | Инцидент не найден |
| `ANA_001` | `ANALYSIS_IN_PROGRESS` | Анализ уже выполняется |
| `ANA_002` | `LLM_RESPONSE_INVALID` | LLM вернула невалидный ответ (исчерпаны retry) |
| `ANA_003` | `METHODOLOGY_NOT_SUPPORTED` | Запрошенная методика ещё не реализована |
| `EXP_001` | `EXPORT_FAILED` | Ошибка генерации PDF/Excel |
| `LIM_001` | `RATE_LIMIT_EXCEEDED` | Превышен лимит запросов к OpenRouter |

---

## 8. Правила для AI-ассистента

- **Не менять** названия и типы полей `IncidentInput`, `RCAResult`, `CauseNode`, `Recommendation` без обновления этого файла
- **Все промпты** должны требовать от LLM формат из раздела 6
- **Новая методика** = новый файл в `src/domain/methodologies/`, наследующий `base.py`; `MethodologyType` enum расширяется здесь
- **Тесты** в `tests/contracts/` должны валидировать каждое поле из разделов 1–3
- **pgvector** используется только для `GET /similar`, не как основное хранилище
