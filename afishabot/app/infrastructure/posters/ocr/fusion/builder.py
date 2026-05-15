from __future__ import annotations

from app.infrastructure.posters.ocr.fusion.evidence import PosterTextEvidence
from app.infrastructure.posters.ocr.models import PosterOCRResult


def build_ocr_evidences(result: PosterOCRResult) -> list[PosterTextEvidence]:
    evidences: list[PosterTextEvidence] = []

    if result.raw_text.strip():
        evidences.append(
            PosterTextEvidence(
                source="ocr_raw_text",
                text=result.raw_text,
                confidence=result.confidence,
                metadata={"kind": "full_text"},
            )
        )

    if result.normalized_text.strip():
        evidences.append(
            PosterTextEvidence(
                source="ocr_normalized_text",
                text=result.normalized_text,
                confidence=result.confidence,
                metadata={"kind": "full_text"},
            )
        )

    for block in result.blocks:
        if not block.text.strip():
            continue

        evidences.append(
            PosterTextEvidence(
                source="ocr_block",
                text=block.text,
                confidence=block.confidence,
                block_type=block.block_type,
                blocks=[block],
                metadata={
                    "reading_order": block.reading_order,
                    "bbox": block.bbox,
                },
            )
        )

    return evidences

