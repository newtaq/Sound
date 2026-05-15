from __future__ import annotations

from typing import Any

from app.services.poster_ocr.models import (
    OCRBackendResult,
    OCRBlock,
    OCRLine,
    OCRLineCandidate,
    OCRWord,
    OCRWordCandidate,
)


def serialize_ocr_backend_result(
    result: OCRBackendResult,
) -> dict[str, Any]:
    return {
        "backend_name": result.backend_name,
        "raw_text": result.raw_text,
        "confidence": result.confidence,
        "blocks": [
            serialize_ocr_block(block)
            for block in result.blocks
        ],
        "metadata": result.metadata,
    }


def serialize_ocr_block(block: OCRBlock) -> dict[str, Any]:
    return {
        "text": block.text,
        "confidence": block.confidence,
        "bbox": list(block.bbox),
        "lines": [
            serialize_ocr_line(line)
            for line in block.lines
        ],
        "block_type": block.block_type,
        "reading_order": block.reading_order,
        "source": block.source,
    }


def serialize_ocr_line(line: OCRLine) -> dict[str, Any]:
    return {
        "text": line.text,
        "confidence": line.confidence,
        "bbox": list(line.bbox),
        "words": [
            serialize_ocr_word(word)
            for word in line.words
        ],
        "candidates": [
            {
                "text": candidate.text,
                "confidence": candidate.confidence,
            }
            for candidate in line.candidates
        ],
        "source": line.source,
    }


def serialize_ocr_word(word: OCRWord) -> dict[str, Any]:
    return {
        "text": word.text,
        "confidence": word.confidence,
        "bbox": list(word.bbox),
        "candidates": [
            {
                "text": candidate.text,
                "confidence": candidate.confidence,
                "language": candidate.language,
            }
            for candidate in word.candidates
        ],
        "language": word.language,
        "source": word.source,
    }


def deserialize_ocr_backend_result(
    payload: dict[str, Any],
) -> OCRBackendResult:
    return OCRBackendResult(
        backend_name=payload["backend_name"],
        raw_text=payload["raw_text"],
        confidence=payload["confidence"],
        blocks=[
            deserialize_ocr_block(item)
            for item in payload.get("blocks", [])
        ],
        metadata=payload.get("metadata", {}),
    )


def deserialize_ocr_block(payload: dict[str, Any]) -> OCRBlock:
    return OCRBlock(
        text=payload["text"],
        confidence=payload["confidence"],
        bbox=tuple(payload["bbox"]),
        lines=[
            deserialize_ocr_line(item)
            for item in payload.get("lines", [])
        ],
        block_type=payload.get("block_type", "unknown"),
        reading_order=payload.get("reading_order", 0),
        source=payload.get("source", ""),
    )


def deserialize_ocr_line(payload: dict[str, Any]) -> OCRLine:
    return OCRLine(
        text=payload["text"],
        confidence=payload["confidence"],
        bbox=tuple(payload["bbox"]),
        words=[
            deserialize_ocr_word(item)
            for item in payload.get("words", [])
        ],
        candidates=[
            OCRLineCandidate(
                text=item["text"],
                confidence=item["confidence"],
            )
            for item in payload.get("candidates", [])
        ],
        source=payload.get("source", ""),
    )


def deserialize_ocr_word(payload: dict[str, Any]) -> OCRWord:
    return OCRWord(
        text=payload["text"],
        confidence=payload["confidence"],
        bbox=tuple(payload["bbox"]),
        chars=[],
        candidates=[
            OCRWordCandidate(
                text=item["text"],
                confidence=item["confidence"],
                language=item.get("language", "unknown"),
            )
            for item in payload.get("candidates", [])
        ],
        language=payload.get("language", "unknown"),
        source=payload.get("source", ""),
    )