from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.posters.ocr.cache.serde import (
    deserialize_ocr_backend_result,
    serialize_ocr_backend_result,
)
from app.infrastructure.posters.ocr.models import OCRBackendResult, PosterImageFingerprint
from app.infrastructure.posters.ocr.protocols import RawOCRCacheStore


class FileRawOCRCacheStore(RawOCRCacheStore):
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def get(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
    ) -> OCRBackendResult | None:
        file_path = self._build_path(
            fingerprint=fingerprint,
            backend_name=backend_name,
            pipeline_version=pipeline_version,
        )
        if not file_path.exists():
            return None

        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return deserialize_ocr_backend_result(payload)

    async def set(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
        result: OCRBackendResult,
    ) -> None:
        file_path = self._build_path(
            fingerprint=fingerprint,
            backend_name=backend_name,
            pipeline_version=pipeline_version,
        )
        payload = serialize_ocr_backend_result(result)
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def delete(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
    ) -> None:
        file_path = self._build_path(
            fingerprint=fingerprint,
            backend_name=backend_name,
            pipeline_version=pipeline_version,
        )
        if not file_path.exists():
            return

        try:
            file_path.unlink()
        except OSError:
            pass

    async def clear(self) -> None:
        for file_path in self.base_dir.glob("*.json"):
            try:
                file_path.unlink()
            except OSError:
                pass

    def _build_path(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        pipeline_version: str,
    ) -> Path:
        filename = f"{fingerprint.sha256}__{backend_name}__{pipeline_version}.json"
        return self.base_dir / filename
    
