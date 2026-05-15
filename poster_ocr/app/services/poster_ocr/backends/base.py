from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.poster_ocr.models import OCRBackendRequest, OCRBackendResult
from app.services.poster_ocr.protocols import OCRBackend


class BaseOCRBackend(ABC, OCRBackend):
    name: str = "base"

    @abstractmethod
    async def recognize(self, request: OCRBackendRequest) -> OCRBackendResult:
        raise NotImplementedError
    