from __future__ import annotations

from app.services.poster_ocr.entities.line_classifier import (
    classify_normalized_block_text,
    resolve_normalized_block_text,
)
from app.services.poster_ocr.layout.word_merge import merge_block_lines
from app.services.poster_ocr.normalize.line_normalizer import normalize_merged_line
from app.services.poster_ocr.result.runtime_dictionary_builder import (
    build_runtime_dictionary,
)
from app.services.poster_ocr.models import OCRBlock, PosterOCRContext


def build_normalized_text(
    blocks: list[OCRBlock],
    context: PosterOCRContext,
) -> str:
    dictionary = build_runtime_dictionary(context)
    normalized_lines: list[str] = []

    for block in blocks:
        merged_text = merge_block_lines(block.lines).strip()
        if not merged_text:
            continue

        normalized_text = normalize_merged_line(
            merged_text,
            dictionary=dictionary,
        ).strip()
        if not normalized_text:
            continue

        resolved_text = resolve_normalized_block_text(
            normalized_text,
            context,
        ).strip()
        if not resolved_text:
            continue

        block.block_type = classify_normalized_block_text(
            resolved_text,
            context,
        )
        normalized_lines.append(resolved_text)

    return "\n".join(normalized_lines)
