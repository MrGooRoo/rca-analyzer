"""
Доменные модели RCA Analyzer.

Источник правды — docs/contracts.md.
НЕ менять имена и типы полей без обновления contracts.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Перечисления
# ---------------------------------------------------------------------------

class SeverityLevel(str, Enum):
    CRITICAL  = "critical"   # Смерть / разрушение оборудования
    MAJOR     = "major"      # Тяжёлая травма / значительный ущерб
    MODERATE  = "moderate"   # Лёгкая травма / умеренный ущерб
    MINOR     = "minor"      # Без травм, незначительный ущерб
    NEAR_MISS = "near_miss"  # Предпосылка к происшествию


class IncidentType(str, Enum):
    INJURY        = "injury"
    EQUIPMENT     = "equipment"
    FIRE          = "fire"
    SPILL         = "spill"
    NEAR_MISS     = "near_miss"
    PROCESS_UPSET = "process_upset"
    SECURITY      = "security"
    ENVIRONMENTAL = "environmental"


class MethodologyType(str, Enum):
    RCA_SYSTEMIC = "rca_systemic"
    FIVE_WHY     = "five_why"
    ISHIKAWA     = "ishikawa"
    FTA          = "fta"
    BOWTIE       = "bowtie"  # планируется


# ---------------------------------------------------------------------------
# Входные данные
# ---------------------------------------------------------------------------

class IncidentInput(BaseModel):
    """Параметры происшествия — входные данные для анализа."""

    title:         str           = Field(..., min_length=5, max_length=200)
    description:   str           = Field(..., min_length=20)
    incident_date: datetime
    location:      str
    incident_type: IncidentType
    severity:      SeverityLevel

    victims:       Optional[int] = Field(None, ge=0)
    equipment:     Optional[str] = None
    conditions:    Optional[str] = None
    actions_taken: Optional[str] = None
    witnesses:     list[str]     = Field(default_factory=list)
    photos:        list[str]     = Field(default_factory=list)
    attachments:   list[str]     = Field(default_factory=list)

    model_config = {"json_schema_extra": {
        "example": {
            "title": "Падение работника с лестницы",
            "description": "Работник поскользнулся на мокрой ступени и упал с высоты 2 м.",
            "incident_date": "2026-06-01T09:30:00",
            "location": "Цех №3, отметка +6м",
            "incident_type": "injury",
            "severity": "moderate",
            "victims": 1,
        }
    }}


class AnalysisRequest(BaseModel):
    """Запрос на запуск анализа."""

    incident:     IncidentInput
    methodology:  MethodologyType = MethodologyType.RCA_SYSTEMIC
    language:     str             = Field("ru", description="Язык отчёта: ru | en")
    detail_level: int             = Field(2, ge=1, le=3,
                                          description="1=кратко, 2=стандарт, 3=подробно")
    user_id:      Optional[str]   = None


# ---------------------------------------------------------------------------
# Выходные данные
# ---------------------------------------------------------------------------

class CauseNode(BaseModel):
    """Узел в дереве причин."""

    id:         str
    text:       str
    category:   str            # человек | процесс | оборудование | среда | управление
    level:      int            # 0=прямая, 1=промежуточная, 2+=корневая
    parent_id:  Optional[str] = None
    confidence: float          = Field(..., ge=0.0, le=1.0)


class Recommendation(BaseModel):
    """Корректирующее мероприятие."""

    id:          str
    text:        str
    priority:    str            # high | medium | low
    category:    str            # immediate | short_term | systemic
    cause_id:    str
    responsible: Optional[str] = None


class RCAResult(BaseModel):
    """Результат анализа корневых причин."""

    result_id:   str
    incident_id: str
    methodology: MethodologyType
    created_at:  datetime

    immediate_causes:    list[CauseNode]
    contributing_causes: list[CauseNode]
    root_causes:         list[CauseNode]
    causal_tree:         list[CauseNode]

    summary:         str
    recommendations: list[Recommendation]

    model_used:     str
    tokens_used:    int
    confidence_avg: float


# ---------------------------------------------------------------------------
# Исключения
# ---------------------------------------------------------------------------

class LLMResponseValidationError(Exception):
    """LLM вернула невалидный JSON (исчерпаны retry)."""


class MethodologyNotSupportedError(Exception):
    """Запрошенная методика ещё не реализована."""
