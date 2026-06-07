# contracts.md — Контракты данных RCA Analyzer

> **Назначение файла:** Единый источник правды для всех модулей проекта.
> Любой новый чат с AI-ассистентом должен получить этот файл как первый контекст.
> Запрещено менять типы и названия полей без обновления этого документа.
>
> **Дата актуализации:** 2026-06-07 (после расширения IncidentInput полями из DOCX, добавления ролей, PDF-экспорта, SSE-прогресса загрузки, chain-of-thought в промптах, fallback моделей).

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
    incident_type: str  # e.g. "injury", "equipment", "fire" и т.д. (см. VALID_TYPES в docx_fields_service)
    severity: str       # "critical" | "major" | "moderate" | "minor" | "near_miss"

    # --- Старые необязательные поля (для обратной совместимости) ---
    victims: Optional[int] = None
    equipment: Optional[str] = None
    conditions: Optional[str] = None
    actions_taken: Optional[str] = None

    # --- Расширенные поля (извлекаются из DOCX-отчётов, используются в промптах всех методологий) ---
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
```

**Примечание:** В старых версиях использовались enum `IncidentType` и `SeverityLevel`. Сейчас — строки (валидация в `docx_fields_service._normalize_fields` и UI). `IncidentInput` в pydantic не имеет строгих enum'ов для этих полей.

---

## 2. Параметры анализа — `AnalysisRequest`

```python
from src.domain.models import MethodologyType, IncidentInput

class AnalysisRequest(BaseModel):
    methodology:  MethodologyType
    language:     str = "ru"    # "ru" | "en"
    detail_level: int = Field(default=2, ge=1, le=3, description="1=кратко, 2=стандарт, 3=подробно")
    incident:     IncidentInput
    # user_id добавляется позже в сервисе/роутере из current_user
```

`MethodologyType` (enum):
- FIVE_WHY
- ISHIKAWA
- FTA
- RCA_SYSTEMIC
- BOWTIE

---

## 3. Выходные данные — `RCAResult`, `CauseNode`, `Recommendation`

```python
from datetime import datetime
from typing import Optional, List
from src.domain.models import MethodologyType

class CauseNode(BaseModel):
    id:         str
    text:       str
    category:   str
    level:      int
    parent_id:  Optional[str] = None
    confidence: float = 0.5

class Recommendation(BaseModel):
    id:          str
    text:        str
    priority:    str
    category:    str
    cause_id:    str
    responsible: Optional[str] = None
    # В БД есть status: "open" | "in_progress" | "closed" (обновляется PATCH)

class RCAResult(BaseModel):
    result_id:           str
    incident_id:         str
    user_id:             Optional[str] = None
    user_display_name:   Optional[str] = None
    user_email:          Optional[str] = None
    methodology:         MethodologyType
    created_at:          datetime

    immediate_causes:    list[CauseNode] = []
    contributing_causes: list[CauseNode] = []
    root_causes:         list[CauseNode] = []
    causal_tree:         list[CauseNode] = []

    summary:             str
    recommendations:     list[Recommendation] = []

    model_used:          str
    tokens_used:         int
    confidence_avg:      float
```

**Примечание по bowtie:** LLM возвращает специализированную структуру (hazard, top_event, threats, prevention_barriers, consequences, mitigation_barriers). `BowTieRunner` нормализует её в стандартный `RCAResult` (threats → root_causes или immediate, barriers → отдельные узлы и т.д.). Аналогично для других методологий.

---

## 4. Схема базы данных (PostgreSQL)

```sql
-- Пользователи (RBAC admin/user)
CREATE TABLE users (
    id             VARCHAR(36) PRIMARY KEY,
    email          VARCHAR(200) UNIQUE NOT NULL,
    display_name   VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(200) NOT NULL,
    role           VARCHAR(20) NOT NULL DEFAULT 'user',  -- 'admin' | 'user'
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- Refresh-токены (для rotation в httpOnly cookie)
CREATE TABLE refresh_tokens (
    id          VARCHAR(36) PRIMARY KEY,
    user_id     VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ
);

-- Инциденты (входные данные; многие расширенные поля хранятся в raw_input JSONB в старых версиях, сейчас частично в колонках + в result)
CREATE TABLE incidents (
    id              VARCHAR(36) PRIMARY KEY,
    user_id         VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    title           VARCHAR(200) NOT NULL,
    description     TEXT NOT NULL,
    incident_date   TIMESTAMPTZ NOT NULL,
    location        VARCHAR(200) NOT NULL,
    incident_type   VARCHAR(50) NOT NULL,
    severity        VARCHAR(50) NOT NULL,
    victims         INTEGER,
    equipment       TEXT,
    conditions      TEXT,
    actions_taken   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Результаты анализа
CREATE TABLE rca_results (
    result_id       VARCHAR(36) PRIMARY KEY,
    incident_id     VARCHAR(36) REFERENCES incidents(id) ON DELETE CASCADE,
    user_id         VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    methodology     VARCHAR(50) NOT NULL,
    summary         TEXT NOT NULL,
    model_used      VARCHAR(100),
    tokens_used     INTEGER,
    confidence_avg  FLOAT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Узлы причин (causal tree)
CREATE TABLE causal_nodes (
    id          VARCHAR(36) PRIMARY KEY,
    result_id   VARCHAR(36) REFERENCES rca_results(result_id) ON DELETE CASCADE,
    node_id     VARCHAR(36),
    node_role   VARCHAR(20),  -- immediate | contributing | root | barrier и т.д.
    text        TEXT NOT NULL,
    category    VARCHAR(100),
    level       INTEGER,
    parent_id   VARCHAR(36),
    confidence  FLOAT
);

-- Рекомендации
CREATE TABLE recommendations (
    id          VARCHAR(36) PRIMARY KEY,
    result_id   VARCHAR(36) REFERENCES rca_results(result_id) ON DELETE CASCADE,
    rec_id      VARCHAR(36),
    text        TEXT NOT NULL,
    priority    VARCHAR(20),
    category    VARCHAR(50),
    cause_id    VARCHAR(36),
    responsible VARCHAR(200),
    status      VARCHAR(20) DEFAULT 'open'  -- open | in_progress | closed
);

-- (pgvector / incident_embeddings — не используется в текущей версии; удалено из активной схемы)
```

Миграции: 001_initial → 005_add_user_role (5 миграций на 07.06.2026).

---

## 5. API-контракты (REST)

**Auth (cookie-based + CSRF):**
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me

**Analysis & Results (требует auth):**
- POST /api/v1/analyze → AnalysisRequest → RCAResult (201)
- GET  /api/v1/results?incident_id=...&limit=...&offset=... → list[RCAResult] (admin — все, user — свои)
- GET  /api/v1/results/{result_id} → RCAResult (owner or admin)
- DELETE /api/v1/results/{result_id} (owner or admin, 204)
- PATCH /api/v1/results/{result_id}/recommendations/{rec_id} → {status}
- GET  /api/v1/methodologies → {"supported": [...]}

**Upload DOCX (требует auth + CSRF):**
- POST /api/v1/upload-report (multipart, file) → ExtractedFields (для автозаполнения формы)
- POST /api/v1/upload-report-stream (SSE для прогресс-бара: reading → analyzing → done с полями)

**Export:**
- GET /api/v1/results/{result_id}/export?format=docx|pdf (скачивание файла)

**Дополнительно:**
- CSRF: signed double-submit cookie `X-CSRF-Token` (кроме exempt: GET, auth bootstrap, Bearer).
- Roles: admin видит/удаляет/редактирует все результаты; user — только свои.

**Response models:** в основном RCAResult / list[RCAResult] / ExtractedFields (см. upload.py).

---

## 6. Формат промпт-контракта (LLM → домен)

LLM **обязана** возвращать строго валидный JSON (с цепочкой рассуждений).

**Общий шаблон (большинство методологий, см. configs/prompts/*.j2):**
```json
{
  "_reasoning": "Цепочка рассуждений (Chain-of-Thought): анализ фактов, построение логики... (обязательно для five_why, bowtie и др.)",
  "immediate_causes": [ { "id": "...", "text": "...", "category": "...", "level": 0, "parent_id": null, "confidence": 0.9 } ],
  "contributing_causes": [ ... ],
  "root_causes": [ ... ],
  "summary": "...",
  "recommendations": [ { "id": "...", "text": "...", "priority": "high|medium|low", "category": "immediate|short_term|systemic", "cause_id": "...", "responsible": "..." } ]
}
```

**Специфично для методологий (LLM-prompt в .j2):**
- `five_why`, `ishikawa`, `fta`, `rca_systemic`: стандартная структура + `_reasoning`.
- `rca_systemic`: дополнительно может возвращать `"barriers": [...]` (парсятся как CauseNode с category="barrier").
- `bowtie`: специализированная структура:
  - `hazard`, `top_event`
  - `threats`, `prevention_barriers` (с `barrier_type`, `degraded`, `threat_id`)
  - `consequences`, `mitigation_barriers` (с `barrier_type`, `degraded`, `consequence_id`)
  - `_reasoning`, `summary`, `recommendations`
- Runner (`src/domain/methodologies/*.py`) валидирует и нормализует в `RCAResult`.

**Валидация:** `LLMResponseValidationError` если отсутствуют обязательные ключи (зависит от runner'а, см. `_validate_response`).

**Правила для промптов:**
- Все `.j2` теперь включают `{% block system %}` / `{% block user %}` (chain-of-thought + блоки).
- Переменные: `request.incident.*` (все расширенные поля), `request.detail_level`, `request.language`.
- Системный промпт требует "Output strictly valid JSON" + язык.

---

## 7. Коды ошибок API

| Код | Константа | Описание |
|-----|-----------|----------|
| (HTTP 400) | `METHODOLOGY_NOT_SUPPORTED` | Запрошенная методика не реализована |
| (HTTP 502) | `LLM_RESPONSE_INVALID` | LLM вернула невалидный JSON после retry |
| (HTTP 404) | `RESULT_NOT_FOUND` / `INCIDENT_NOT_FOUND` | Не найден результат/инцидент |
| (HTTP 403) | (owner-or-admin) | Доступ запрещён (не владелец и не admin) |
| (HTTP 401/403) | CSRF / Auth | Ошибки авторизации / CSRF |
| (HTTP 413) | File too large | Для upload-report |

В коде используются HTTPException с detail (не всегда с кодом).

---

## 8. Правила для AI-ассистента

- **Читай этот файл (`docs/contracts.md`) перед любыми изменениями** — там все типы данных.
- **Не изобретай свои структуры данных** — используй модели из `src/domain/models.py` (и этот документ).
- **Новая методика** → новый файл в `src/domain/methodologies/`, наследует `base.py`; обнови `MethodologyType` и `_RUNNERS` в analysis_service; обнови промпт в `configs/prompts/`.
- **Промпты** хранятся в `configs/prompts/*.j2` (Jinja2, с блоками system/user + _reasoning).
- **После изменений** обновляй `docs/state.md`, `README.md` (если нужно), этот файл.
- **Тесты** для новых модулей — обязательно (unit + integration/E2E где возможно).
- **DOCX-поля:** при изменениях в IncidentInput — синхронизировать `SYSTEM_PROMPT` / `USER_PROMPT_TEMPLATE` в `docx_fields_service.py`, `ExtractedFields` в upload.py, UI (IncidentForm.jsx), и тесты.
- **Роли:** admin/user — изоляция на уровне роутеров (`_check_owner_or_admin`), репозитория и JWT.
- **Кэширование / fallback:** (если добавляется) — документировать здесь.
- **pgvector** в текущей версии не используется (удалён из активных контрактов).

**Конвенции:**
- Все даты/время в UTC (TIMESTAMPTZ в БД, datetime в pydantic).
- ID — UUID strings (str).
- В UI и экспорте используются нормализованные RCAResult.
- При обновлении моделей — обновлять `tests/contracts/test_models.py` (если нужно) и этот файл.

---

**История изменений (кратко):**
- 2026-06-07: Актуализировано под расширенный IncidentInput (20+ полей + Victim), адаптивный DOCX, chain-of-thought в промптах, роли в RCAResult/DB, текущие API эндпоинты, bowtie-специфичный формат, удалены устаревшие enum'ы и pgvector.
- Ранее: добавлены PDF, CSRF, роли, E2E-тесты и т.д.

> **Важно:** Если LLM вернула невалидный JSON — `analysis_service` / runner выбрасывает `LLMResponseValidationError` и (в клиенте) делает повторный запрос.
