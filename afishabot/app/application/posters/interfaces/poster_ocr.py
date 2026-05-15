from __future__ import annotations

from typing import Protocol

from app.infrastructure.posters.ocr.models import PosterOCRRequest, PosterOCRResult


class PosterOCRService(Protocol):
    async def recognize(self, request: PosterOCRRequest) -> PosterOCRResult:
        ...
        