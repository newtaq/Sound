from __future__ import annotations

from dataclasses import dataclass, field

from app.infrastructure.posters.ocr.fusion.evidence import PosterTextEvidence


@dataclass(slots=True)
class PosterFusionOutput:
    evidences: list[PosterTextEvidence] = field(default_factory=list)
    
