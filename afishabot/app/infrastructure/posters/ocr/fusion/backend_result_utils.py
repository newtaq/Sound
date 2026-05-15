from __future__ import annotations

from app.infrastructure.posters.ocr.models import OCRBackendResult


def is_backend_result_successful(result: OCRBackendResult) -> bool:
    metadata = result.metadata or {}
    return not metadata.get("error") and bool(
        result.raw_text.strip() or result.blocks
    )


def build_raw_text(results: list[OCRBackendResult]) -> str:
    return "\n".join(
        result.raw_text.strip()
        for result in results
        if result.raw_text.strip()
    )


def build_confidence(results: list[OCRBackendResult]) -> float:
    if not results:
        return 0.0

    return max(result.confidence for result in results)

