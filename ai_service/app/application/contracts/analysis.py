from dataclasses import dataclass, field as dataclass_field
from typing import Any

from app.application.contracts.sql_plan import AISqlPlanItem


@dataclass(slots=True)
class AIParsedAnalysis:
    ok: bool
    data: dict[str, Any] | None = None
    raw_text: str = ""
    error: str | None = None
    warnings: list[str] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class AIEvidence:
    field: str
    value: Any
    source: str | None = None
    source_text: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class AIDecision:
    type: str
    confidence: float | None = None
    data: dict[str, Any] = dataclass_field(default_factory=dict)
    evidence: list[AIEvidence] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class AIAnalysisResult:
    content_type: str
    is_useful: bool
    priority: str
    confidence: float
    main_decision: str
    decisions: list[AIDecision] = dataclass_field(default_factory=list)
    variants: list[dict[str, Any]] = dataclass_field(default_factory=list)
    sql_plan: list[AISqlPlanItem] = dataclass_field(default_factory=list)
    warnings: list[str] = dataclass_field(default_factory=list)
    raw: dict[str, Any] = dataclass_field(default_factory=dict)
    

