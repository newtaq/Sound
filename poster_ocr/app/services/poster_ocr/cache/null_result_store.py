from __future__ import annotations

from app.services.poster_ocr.protocols import PosterOCRResultStore
from app.services.poster_ocr.models import PosterImageFingerprint, PosterOCRResult


class NullPosterOCRResultStore(PosterOCRResultStore):
    async def get(
        self,
        fingerprint: PosterImageFingerprint,
        pipeline_version: str,
    ) -> PosterOCRResult | None:
        return None

    async def save(
        self,
        fingerprint: PosterImageFingerprint,
        pipeline_version: str,
        result: PosterOCRResult,
    ) -> None:
        return None
    