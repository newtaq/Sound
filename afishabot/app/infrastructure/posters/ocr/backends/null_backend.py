from __future__ import annotations

from app.infrastructure.posters.ocr.backends.base import BaseOCRBackend
from app.infrastructure.posters.ocr.models import OCRBackendRequest, OCRBackendResult


class NullOCRBackend(BaseOCRBackend):
    name = "null"

    async def recognize(self, request: OCRBackendRequest) -> OCRBackendResult:
        return OCRBackendResult(
            backend_name=self.name,
            raw_text="",
            confidence=0.0,
            blocks=[],
            metadata={},
        )
        
