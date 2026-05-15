from __future__ import annotations

import hashlib

from app.infrastructure.posters.ocr.protocols import FingerprintService
from app.infrastructure.posters.ocr.models import PosterImage, PosterImageFingerprint


class SimpleFingerprintService(FingerprintService):
    async def build(self, image: PosterImage) -> PosterImageFingerprint:
        return PosterImageFingerprint(
            sha256=self._build_sha256(image.data),
            phash=None,
            width=image.width,
            height=image.height,
        )

    def _build_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
    
