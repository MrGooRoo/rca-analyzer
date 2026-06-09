"""
Pydantic domain-модели RCA Analyzer.
"""

from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class MethodologyType(str, Enum):
    FIVE_WHY     = "five_why"
    ISHIKAWA     = "ishikawa"
    FTA          = "fta"
    RCA_SYSTEMIC = "rca_systemic"
    BOWTIE       = "bowtie"


class Victim(BaseModel):
    """Сведения о пострадавшем"""
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
    # --- Старые поля (оставлены для обратной совместимости) ---
    title: str
    description: str
    incident_date: datetime | None = None
    location: str = ""
    incident_type: str
    severity: str
    victims: Optional[int] = None
    equipment: Optional[str] = None
    conditions: Optional[str] = None
    actions_taken: Optional[str] = None

    # --- Новые расширенные поля ---
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


class AnalysisRequest(BaseModel):
    methodology:  MethodologyType
    language:     str           = "ru"
    detail_level: int           = Field(default=2, ge=1, le=3)
    incident:     IncidentInput


class CauseNode(BaseModel):
    id:         str
    text:       str
    category:   str
    level:      int
    parent_id:  Optional[str]   = None
    confidence: float           = 0.5


class Recommendation(BaseModel):
    id:          str
    text:        str
    priority:    str
    category:    str
    cause_id:    str
    responsible: Optional[str]  = None


class RCAResult(BaseModel):
    result_id:           str
    incident_id:         str
    user_id:             Optional[str]              = None
    user_display_name:   Optional[str]              = None
    user_email:          Optional[str]              = None
    methodology:         MethodologyType
    created_at:          datetime
    immediate_causes:    list[CauseNode]            = []
    contributing_causes: list[CauseNode]            = []
    root_causes:         list[CauseNode]            = []
    causal_tree:         list[CauseNode]            = []
    summary:             str
    recommendations:     list[Recommendation]       = []
    model_used:          str
    tokens_used:         int
    confidence_avg:      float


class MethodologyNotSupportedError(Exception):
    pass


class LLMResponseValidationError(Exception):
    pass

# ----------------------------------------------------------------------
# Сравнение методик (добавлено 08.06.2026)
# ----------------------------------------------------------------------

class MultiAnalysisRequest(BaseModel):
    methodologies: list[MethodologyType] = Field(..., min_length=2, max_length=5)
    language: str = "ru"
    detail_level: int = Field(default=2, ge=1, le=3)
    incident: IncidentInput

    @field_validator('methodologies')
    @classmethod
    def validate_unique_methodologies(cls, v):
        """Убедиться, что методики не повторяются."""
        if len(v) != len(set(v)):
            raise ValueError('Методики не должны повторяться')
        return v


class ComparisonResult(BaseModel):
    incident_id: str
    results: list[RCAResult]
    common_recommendations: list[Recommendation] = Field(default_factory=list)
    differing_causes: dict[str, list[str]] = Field(default_factory=dict)
    summary: str = ""