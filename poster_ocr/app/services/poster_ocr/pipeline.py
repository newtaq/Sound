from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.poster_ocr.backends.factory import build_default_ocr_backends
from app.services.poster_ocr.backends.null_backend import NullOCRBackend
from app.services.poster_ocr.cache.file_raw_cache import FileRawOCRCacheStore
from app.services.poster_ocr.cache.fingerprints import SimpleFingerprintService
from app.services.poster_ocr.cache.null_result_store import NullPosterOCRResultStore
from app.services.poster_ocr.config import PosterOCRConfig, build_poster_ocr_config
from app.services.poster_ocr.fusion.backend_result_utils import (
    build_confidence,
    build_raw_text,
    is_backend_result_successful,
)
from app.services.poster_ocr.fusion.block_fuser import fuse_blocks
from app.services.poster_ocr.fusion.result_persistence import should_persist_result
from app.services.poster_ocr.models import (
    OCRBackendRequest,
    OCRBackendResult,
    OCRBlock,
    PosterDebugData,
    PosterImageFingerprint,
    PosterOCRContext,
    PosterOCRRequest,
    PosterOCRResult,
)
from app.services.poster_ocr.protocols import (
    FingerprintService,
    OCRBackend,
    PosterOCRResultStore,
    RawOCRCacheStore,
)
from app.services.poster_ocr.result.normalized_text_builder import (
    build_normalized_text,
)


class PosterOCRPipeline:
    def __init__(
        self,
        config: PosterOCRConfig | None = None,
        fingerprint_service: FingerprintService | None = None,
        result_store: PosterOCRResultStore | None = None,
        raw_cache_store: RawOCRCacheStore | None = None,
        backends: list[OCRBackend] | None = None,
    ) -> None:
        self.config = config or build_poster_ocr_config()
        self.fingerprint_service = fingerprint_service or SimpleFingerprintService()
        self.result_store = result_store or NullPosterOCRResultStore()
        self.raw_cache_store = raw_cache_store or FileRawOCRCacheStore(
            Path(".cache") / "poster_ocr" / "raw"
        )
        self.backends = self._resolve_backends(backends)

    async def run(self, request: PosterOCRRequest) -> PosterOCRResult:
        fingerprint = await self._build_fingerprint(request)

        cached_pipeline_result = await self._load_pipeline_result(fingerprint)
        if cached_pipeline_result is not None:
            return cached_pipeline_result

        backend_results, backend_debug = await self._execute_backends(
            request=request,
            fingerprint=fingerprint,
        )

        successful_results = self._filter_successful_backend_results(backend_results)

        result = self._assemble_pipeline_result(
            fingerprint=fingerprint,
            backend_results=backend_results,
            successful_results=successful_results,
            backend_debug=backend_debug,
            context=request.context,
        )

        await self._save_pipeline_result_if_needed(
            fingerprint=fingerprint,
            result=result,
        )

        return result

    def _resolve_backends(
        self,
        backends: list[OCRBackend] | None,
    ) -> list[OCRBackend]:
        resolved_backends = backends or build_default_ocr_backends(self.config)

        if resolved_backends:
            return resolved_backends

        return [NullOCRBackend()]

    async def _build_fingerprint(
        self,
        request: PosterOCRRequest,
    ) -> PosterImageFingerprint:
        return await self.fingerprint_service.build(request.image)

    async def _load_pipeline_result(
        self,
        fingerprint: PosterImageFingerprint,
    ) -> PosterOCRResult | None:
        return await self.result_store.get(
            fingerprint=fingerprint,
            pipeline_version=self.config.pipeline_version,
        )

    async def _execute_backends(
        self,
        request: PosterOCRRequest,
        fingerprint: PosterImageFingerprint,
    ) -> tuple[list[OCRBackendResult], dict[str, dict[str, Any]]]:
        results: list[OCRBackendResult] = []
        debug_map: dict[str, dict[str, Any]] = {}

        for backend in self.backends:
            backend_name = self._get_backend_name(backend)

            try:
                result, debug_info = await self._execute_single_backend(
                    backend=backend,
                    request=request,
                    fingerprint=fingerprint,
                )
            except Exception as exc:
                result = self._build_backend_exception_result(
                    backend_name=backend_name,
                    exc=exc,
                )
                debug_info = self._build_backend_debug_info(
                    source="pipeline",
                    result=result,
                )

            results.append(result)
            debug_map[backend_name] = debug_info

            if self._should_stop_after_backend(result):
                break

        return results, debug_map

    def _should_stop_after_backend(
        self,
        result: OCRBackendResult,
    ) -> bool:
        if self.config.backend_execution_mode != "first_success":
            return False

        return is_backend_result_successful(result)

    async def _execute_single_backend(
        self,
        backend: OCRBackend,
        request: PosterOCRRequest,
        fingerprint: PosterImageFingerprint,
    ) -> tuple[OCRBackendResult, dict[str, Any]]:
        backend_name = self._get_backend_name(backend)

        cached_result = await self._load_backend_cached_result(
            fingerprint=fingerprint,
            backend_name=backend_name,
        )
        if cached_result is not None:
            return cached_result, self._build_backend_debug_info(
                source="raw_cache",
                result=cached_result,
            )

        backend_result = await self._call_backend(
            backend=backend,
            request=request,
        )

        if is_backend_result_successful(backend_result):
            await self._save_backend_cached_result(
                fingerprint=fingerprint,
                backend_name=backend_name,
                result=backend_result,
            )

        return backend_result, self._build_backend_debug_info(
            source="backend",
            result=backend_result,
        )

    async def _load_backend_cached_result(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
    ) -> OCRBackendResult | None:
        return await self.raw_cache_store.get(
            fingerprint=fingerprint,
            backend_name=backend_name,
            pipeline_version=self.config.pipeline_version,
        )

    async def _save_backend_cached_result(
        self,
        fingerprint: PosterImageFingerprint,
        backend_name: str,
        result: OCRBackendResult,
    ) -> None:
        await self.raw_cache_store.set(
            fingerprint=fingerprint,
            backend_name=backend_name,
            pipeline_version=self.config.pipeline_version,
            result=result,
        )

    async def _call_backend(
        self,
        backend: OCRBackend,
        request: PosterOCRRequest,
    ) -> OCRBackendResult:
        backend_request = OCRBackendRequest(
            image=request.image,
            context=request.context,
            block=None,
            debug=request.debug,
        )

        result = await backend.recognize(backend_request)
        result.backend_name = self._resolve_result_backend_name(
            result=result,
            backend=backend,
        )
        return result

    def _filter_successful_backend_results(
        self,
        backend_results: list[OCRBackendResult],
    ) -> list[OCRBackendResult]:
        return [
            result
            for result in backend_results
            if is_backend_result_successful(result)
        ]

    def _assemble_pipeline_result(
        self,
        fingerprint: PosterImageFingerprint,
        backend_results: list[OCRBackendResult],
        successful_results: list[OCRBackendResult],
        backend_debug: dict[str, dict[str, Any]],
        context: PosterOCRContext,
    ) -> PosterOCRResult:
        blocks = fuse_blocks(successful_results)
        raw_text = self._build_pipeline_raw_text(successful_results, blocks)
        normalized_text = self._build_pipeline_normalized_text(blocks, context)
        confidence = self._build_pipeline_confidence(successful_results, blocks)
        debug = self._build_pipeline_debug(
            backend_results=backend_results,
            successful_results=successful_results,
            backend_debug=backend_debug,
            blocks_count=len(blocks),
        )

        return PosterOCRResult(
            raw_text=raw_text,
            normalized_text=normalized_text,
            confidence=confidence,
            blocks=blocks,
            entity_hints=[],
            fingerprint=fingerprint,
            debug=debug,
        )

    def _build_pipeline_raw_text(
        self,
        successful_results: list[OCRBackendResult],
        blocks: list[OCRBlock],
    ) -> str:
        block_text = "\n".join(
            block.text.strip()
            for block in blocks
            if block.text.strip()
        )
        if block_text:
            return block_text

        return build_raw_text(successful_results)

    def _build_pipeline_normalized_text(
        self,
        blocks: list[OCRBlock],
        context: PosterOCRContext,
    ) -> str:
        return build_normalized_text(
            blocks=blocks,
            context=context,
        )

    def _build_pipeline_confidence(
        self,
        successful_results: list[OCRBackendResult],
        blocks: list[OCRBlock],
    ) -> float:
        if blocks:
            return max(block.confidence for block in blocks)

        return build_confidence(successful_results)

    def _build_pipeline_debug(
        self,
        backend_results: list[OCRBackendResult],
        successful_results: list[OCRBackendResult],
        backend_debug: dict[str, dict[str, Any]],
        blocks_count: int,
    ) -> PosterDebugData:
        return PosterDebugData(
            values={
                "pipeline_version": self.config.pipeline_version,
                "backend_execution_mode": self.config.backend_execution_mode,
                "backend_results_count": len(backend_results),
                "successful_backend_results_count": len(successful_results),
                "backend_names": [
                    result.backend_name
                    for result in backend_results
                ],
                "backend_debug": backend_debug,
                "blocks_count": blocks_count,
            }
        )

    async def _save_pipeline_result_if_needed(
        self,
        fingerprint: PosterImageFingerprint,
        result: PosterOCRResult,
    ) -> None:
        if not should_persist_result(result):
            return

        await self.result_store.save(
            fingerprint=fingerprint,
            pipeline_version=self.config.pipeline_version,
            result=result,
        )

    def _build_backend_debug_info(
        self,
        source: str,
        result: OCRBackendResult,
    ) -> dict[str, Any]:
        return {
            "source": source,
            "success": is_backend_result_successful(result),
            "metadata": result.metadata,
        }

    def _build_backend_exception_result(
        self,
        backend_name: str,
        exc: Exception,
    ) -> OCRBackendResult:
        return OCRBackendResult(
            backend_name=backend_name,
            raw_text="",
            confidence=0.0,
            blocks=[],
            metadata={
                "error": "pipeline_backend_error",
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            },
        )

    def _get_backend_name(
        self,
        backend: OCRBackend,
    ) -> str:
        name = getattr(backend, "name", None)
        if isinstance(name, str) and name.strip():
            return name

        backend_name = getattr(backend, "backend_name", None)
        if isinstance(backend_name, str) and backend_name.strip():
            return backend_name

        return backend.__class__.__name__

    def _resolve_result_backend_name(
        self,
        result: OCRBackendResult,
        backend: OCRBackend,
    ) -> str:
        if getattr(result, "backend_name", ""):
            return result.backend_name

        return self._get_backend_name(backend)
    