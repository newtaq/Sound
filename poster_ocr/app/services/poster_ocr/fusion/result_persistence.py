from __future__ import annotations

from app.services.poster_ocr.models import PosterOCRResult


def should_persist_result(result: PosterOCRResult) -> bool:
    return bool(result.raw_text.strip() or result.blocks)
