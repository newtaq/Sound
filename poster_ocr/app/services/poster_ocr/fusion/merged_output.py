from __future__ import annotations

from dataclasses import dataclass, field

from app.services.poster_ocr.fusion.evidence import PosterTextEvidence


@dataclass(slots=True)
class PosterFusionOutput:
    evidences: list[PosterTextEvidence] = field(default_factory=list)
    