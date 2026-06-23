"""
Pydantic domain-модели RCA Analyzer.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class MethodologyType(StrEnum):
    FIVE_WHY     = "five_why"
    ISHIKAWA     = "ishikawa"
    FTA          = "fta"
    RCA_SYSTEMIC = "rca_systemic"
    BOWTIE       = "bowtie"


class Victim(BaseModel):
    """Сведения о пострадавшем"""
    full_name: str | None = Field(default=None, max_length=200)
    birth_date: date | None = None
    age: int | None = None
    family_status: str | None = Field(default=None, max_length=100)
    children_under_21: int | None = None
    profession: str | None = Field(default=None, max_length=200)
    workplace: str | None = Field(default=None, max_length=200)
    total_experience: str | None = Field(default=None, max_length=100)
    experience_in_organization: str | None = Field(default=None, max_length=100)
    qualification_certificate: str | None = Field(default=None, max_length=200)
    introductory_briefing: str | None = Field(default=None, max_length=100)
    workplace_briefing: str | None = Field(default=None, max_length=100)
    internship: str | None = Field(default=None, max_length=100)
    safety_knowledge_test: str | None = Field(default=None, max_length=100)
    medical_examination: str | None = Field(default=None, max_length=100)
    diagnosis_severity: str | None = Field(default=None, max_length=200)

    @field_validator('birth_date', mode='before')
    @classmethod
    def parse_birth_date(cls, v: Any) -> date | None:
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
    title: str = Field(..., max_length=500)
    description: str = Field(..., max_length=10000)
    incident_date: datetime | None = None
    location: str = Field(default="", max_length=500)
    incident_type: str = Field(..., max_length=100)
    severity: str = Field(..., max_length=50)
    victims: int | None = None
    equipment: str | None = Field(default=None, max_length=500)
    conditions: str | None = Field(default=None, max_length=2000)
    actions_taken: str | None = Field(default=None, max_length=5000)

    # --- Новые расширенные поля ---
    incident_time: time | None = None
    company: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    location_detailed: str | None = Field(default=None, max_length=500)
    injured_count: int | None = None
    fatalities_count: int | None = None
    short_description: str | None = Field(default=None, max_length=2000)
    photo_urls: list[str] = Field(default_factory=list)
    victims_list: list[Victim] = Field(default_factory=list)
    scene_description: str | None = Field(default=None, max_length=10000)
    equipment_description: str | None = Field(default=None, max_length=5000)
    full_circumstances: str | None = Field(default=None, max_length=20000)
    established_facts: str | None = Field(default=None, max_length=20000)


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
    parent_id:  str | None   = None
    confidence: float           = 0.5


class Recommendation(BaseModel):
    id:          str
    text:        str
    priority:    str
    category:    str
    cause_id:    str
    responsible: str | None  = None
    status: str              = "open"


class RCAResult(BaseModel):
    result_id:           str
    incident_id:         str
    session_id:          str | None              = None
    user_id:             str | None              = None
    user_display_name:   str | None              = None
    user_email:          str | None              = None
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
    # P17 LLM Conductor provenance (optional for backward compatibility)
    draft_model_used:       str | None = None
    verifier_model_used:    str | None = None
    draft_tokens_used:      int | None = None
    verifier_tokens_used:   int | None = None
    verification_applied:   bool = False
    verification_reason:    str | None = None


# ----------------------------------------------------------------------
# P17 — LLM Conductor settings (admin-managed, planned conductor runtime)
# ----------------------------------------------------------------------

VerificationScheme = Literal["disabled", "threshold", "always"]

_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9._~:/-]{1,200}$")


def _normalize_model_id(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ValueError("Model id is required")
        return None
    normalized = value.strip()
    if not normalized:
        if required:
            raise ValueError("Model id is required")
        return None
    if not _MODEL_ID_RE.fullmatch(normalized):
        raise ValueError("Model id must be an OpenRouter slug without spaces")
    return normalized


class LLMSettingsUpdate(BaseModel):
    """Payload for admin-managed LLM conductor settings."""

    draft_model: str
    verifier_model: str | None = None
    quality_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    verification_scheme: VerificationScheme = "threshold"

    @field_validator("draft_model", mode="before")
    @classmethod
    def validate_draft_model(cls, value: str | None) -> str:
        normalized = _normalize_model_id(value, required=True)
        assert normalized is not None
        return normalized

    @field_validator("verifier_model", mode="before")
    @classmethod
    def validate_verifier_model(cls, value: str | None) -> str | None:
        return _normalize_model_id(value, required=False)

    @model_validator(mode="after")
    def validate_verifier_required(self) -> LLMSettingsUpdate:
        if self.verification_scheme != "disabled" and not self.verifier_model:
            raise ValueError("verifier_model is required unless verification_scheme is disabled")
        return self


class LLMSettings(LLMSettingsUpdate):
    """Current LLM conductor settings returned by admin API."""

    updated_at: datetime | None = None
    updated_by: str | None = None


class OpenRouterModelInfo(BaseModel):
    """OpenRouter catalog item for future admin model picker."""

    id: str
    name: str | None = None
    context_length: int | None = None
    prompt_price_per_1m: float | None = None
    completion_price_per_1m: float | None = None
    is_free: bool = False


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
    def validate_unique_methodologies(cls, v: list[MethodologyType]) -> list[MethodologyType]:
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


class MethodologyFailure(BaseModel):
    """Информация об упавшей методике в multi-анализе."""
    methodology: MethodologyType
    error: str


class MultiAnalysisResponse(BaseModel):
    """Результат multi-анализа: успешные результаты + список ошибок по методикам."""
    results: list[RCAResult] = Field(default_factory=list)
    failures: list[MethodologyFailure] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Сущность «исследование» (добавлено 13.06.2026)
# ----------------------------------------------------------------------

class AnalysisSession(BaseModel):
    """Логическая группа анализов одного инцидента."""
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
    incident_hash:          str | None              = None
    results:                list[RCAResult]         = Field(default_factory=list)


# ----------------------------------------------------------------------
# Похожие инциденты / RAG (добавлено 10.06.2026, приоритет D)
# ----------------------------------------------------------------------

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
    # Описание инцидента для контекста (из сессии)
    incident_title: str | None = None
    incident_description: str | None = None
    incident_date: datetime | None = None
    incident_location: str | None = None