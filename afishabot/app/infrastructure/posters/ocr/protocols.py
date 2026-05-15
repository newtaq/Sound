from __future__ import annotations

from typing import Protocol

from app.infrastructure.posters.ocr.models import (
    OCRBackendRequest,
    OCRBackendResult,
    PosterImage,
    PosterImageFingerprint,
    PosterOCRResult,
)


class OCRBackend(Protocol):
    name: str

    async def recognize(self, request: OCRBackendRequest) -> OCRBackendResult:
        ...


class FingerprintService(Protocol):
    async def build(self, image: PosterImage) -> PosterImageFingerprint:
        ...


class RawOCRCacheStore(Protocol):
    async def get(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
    ) -> OCRBackendResult | None:
        ...

    async def set(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
        result: OCRBackendResult,
    ) -> None:
        ...

    async def delete(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
    ) -> None:
        ...

    async def clear(self) -> None:
        ...


class PosterOCRResultStore(Protocol):
    async def get(
        self,
        fingerprint: PosterImageFingerprint,
        pipeline_version: str,
    ) -> PosterOCRResult | None:
        ...

    async def save(
        self,
        fingerprint: PosterImageFingerprint,
        pipeline_version: str,
        result: PosterOCRResult,
    ) -> None:
        ...


