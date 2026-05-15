from __future__ import annotations

from dataclasses import dataclass, field

from app.services.poster_ocr.models import OCRBlock


@dataclass(slots=True)
class PosterTextEvidence:
    source: str
    text: str
    confidence: float
    block_type: str | None = None
    blocks: list[OCRBlock] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    