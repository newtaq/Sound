from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.services.poster_ocr.config import PosterOCRConfig
from app.services.poster_ocr.confusion.token_variants import generate_token_variants
from app.services.poster_ocr.pipeline import PosterOCRPipeline
from app.services.poster_ocr.models import (
    EntityCandidate,
    OCRBlock,
    OCRLine,
    OCRWord,
    PosterImage,
    PosterOCRContext,
    PosterOCRRequest,
)


def build_request(image_path: Path) -> PosterOCRRequest:
    data = image_path.read_bytes()

    image = PosterImage(
        data=data,
        filename=image_path.name,
        mime_type=_guess_mime_type(image_path),
    )

    context = PosterOCRContext(
        description_text=_build_test_description(),
        entity_candidates=_build_test_entity_candidates(),
    )

    return PosterOCRRequest(
        image=image,
        context=context,
        debug=True,
    )


def _build_test_description() -> str:
    return "\n".join(
        [
            "Кишлак",
            "Москва",
            "Санкт-Петербург",
            "МТС Live Холл",
            "Temple of Deer",
        ]
    )


def _build_test_entity_candidates() -> list[EntityCandidate]:
    return [
        EntityCandidate(
            entity_type="artist",
            name="Кишлак",
            aliases=["KISHLAK", "Kishlak"],
            source="test_context",
        ),
        EntityCandidate(
            entity_type="city",
            name="Москва",
            aliases=["Moscow"],
            source="test_context",
        ),
        EntityCandidate(
            entity_type="city",
            name="Санкт-Петербург",
            aliases=["Санкт Петербург", "Saint Petersburg"],
            source="test_context",
        ),
        EntityCandidate(
            entity_type="venue",
            name="МТС Live Холл",
            aliases=["МТС Live Hall", "MTS Live Hall", "MTC Live Hall"],
            source="test_context",
        ),
        EntityCandidate(
            entity_type="venue",
            name="Temple of Deer",
            aliases=["temple of deer"],
            source="test_context",
        ),
    ]


def _guess_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"

    return "application/octet-stream"


def _print_blocks(blocks: list[OCRBlock]) -> None:
    print("=" * 80)
    print("BLOCKS")
    print("=" * 80)

    if not blocks:
        print("<empty>")
        print()
        return

    for index, block in enumerate(blocks, start=1):
        print(
            f"[BLOCK {index}] text={block.text!r} "
            f"conf={block.confidence:.3f} "
            f"bbox={block.bbox} "
            f"type={block.block_type!r} "
            f"order={block.reading_order}"
        )

        for line_index, line in enumerate(block.lines, start=1):
            _print_line(line_index, line)

        print()


def _print_line(index: int, line: OCRLine) -> None:
    print(
        f"  [LINE {index}] text={line.text!r} "
        f"conf={line.confidence:.3f} "
        f"bbox={line.bbox}"
    )

    for word_index, word in enumerate(line.words, start=1):
        _print_word(word_index, word)


def _print_word(index: int, word: OCRWord) -> None:
    print(
        f"    [WORD {index}] text={word.text!r} "
        f"conf={word.confidence:.3f} "
        f"bbox={word.bbox} "
        f"lang={word.language!r}"
    )

    variants = generate_token_variants(word.text, limit=6)
    if variants:
        print(f"      variants={variants}")


def _print_context(request: PosterOCRRequest) -> None:
    print("=" * 80)
    print("CONTEXT")
    print("=" * 80)

    if request.context.description_text:
        print("DESCRIPTION:")
        print(request.context.description_text)
        print()

    if request.context.entity_candidates:
        print("ENTITY CANDIDATES:")
        for candidate in request.context.entity_candidates:
            print(
                f"- type={candidate.entity_type!r} "
                f"name={candidate.name!r} "
                f"aliases={candidate.aliases}"
            )
        print()


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: py -m scripts.poster_ocr.test_pipeline <image_path>")
        raise SystemExit(1)

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"File not found: {image_path}")
        raise SystemExit(1)

    from app.services.poster_ocr.config import build_poster_ocr_config

    config = build_poster_ocr_config()
    pipeline = PosterOCRPipeline(config=config)

    request = build_request(image_path)
    result = await pipeline.run(request)

    _print_context(request)

    print("=" * 80)
    print("RAW TEXT")
    print("=" * 80)
    print(result.raw_text or "<empty>")
    print()

    print("=" * 80)
    print("NORMALIZED TEXT")
    print("=" * 80)
    print(result.normalized_text or "<empty>")
    print()

    print("=" * 80)
    print("CONFIDENCE")
    print("=" * 80)
    print(result.confidence)
    print()

    _print_blocks(result.blocks)

    print("=" * 80)
    print("DEBUG")
    print("=" * 80)
    print(result.debug.values)


if __name__ == "__main__":
    asyncio.run(main())
    
    