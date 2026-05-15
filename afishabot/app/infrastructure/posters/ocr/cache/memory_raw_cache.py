from __future__ import annotations

from app.infrastructure.posters.ocr.models import OCRBackendResult, PosterImageFingerprint
from app.infrastructure.posters.ocr.protocols import RawOCRCacheStore


class MemoryRawOCRCacheStore(RawOCRCacheStore):
    def __init__(self) -> None:
        self._storage: dict[str, OCRBackendResult] = {}

    async def get(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
    ) -> OCRBackendResult | None:
        key = self._build_key(
            fingerprint=fingerprint,
            backend_name=backend_name,
            pipeline_version=pipeline_version,
        )
        return self._storage.get(key)

    async def set(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
        result: OCRBackendResult,
    ) -> None:
        key = self._build_key(
            fingerprint=fingerprint,
            backend_name=backend_name,
            pipeline_version=pipeline_version,
        )
        self._storage[key] = result

    async def delete(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
    ) -> None:
        key = self._build_key(
            fingerprint=fingerprint,
            backend_name=backend_name,
            pipeline_version=pipeline_version,
        )
        self._storage.pop(key, None)

    async def clear(self) -> None:
        self._storage.clear()

    def _build_key(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
    ) -> str:
        return f"{fingerprint.sha256}:{backend_name}:{pipeline_version}"
    
