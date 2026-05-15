from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AISqlPlanItem:
    sql: str
    purpose: str | None = None
    confidence: float | None = None
    requires_review: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    

