"""
Pydantic domain-модели RCA Analyzer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MethodologyType(str, Enum):
    FIVE_WHY     = "five_why"
    ISHIKAWA     = "ishikawa"
    FTA          = "fta"
    RCA_SYSTEMIC = "rca_systemic"
    BOWTIE       = "bowtie"


class IncidentInput(BaseModel):
    title:         str
    description:   str
    incident_date: datetime
    location:      str
    incident_type: str
    severity:      str
    victims:       Optional[int]  = None
    equipment:     Optional[str]  = None
    conditions:    Optional[str]  = None
    actions_taken: Optional[str]  = None


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
