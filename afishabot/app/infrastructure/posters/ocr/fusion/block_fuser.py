from __future__ import annotations

import re

from app.infrastructure.posters.ocr.models import OCRBackendResult, OCRBlock


_MIN_BLOCK_CONFIDENCE = 0.30
_MIN_BLOCK_TEXT_LENGTH = 2


def fuse_blocks(successful_results: list[OCRBackendResult]) -> list[OCRBlock]:
    collected: list[OCRBlock] = []

    for backend_result in successful_results:
        for block in backend_result.blocks:
            cloned = clone_block(block)
            if not accept_block(cloned):
                continue
            collected.append(cloned)

    if not collected:
        return []

    groups = group_overlapping_blocks(collected)
    fused_blocks = [choose_best_block(group) for group in groups]
    fused_blocks = [
        block
        for block in fused_blocks
        if accept_block(block)
    ]
    fused_blocks.sort(key=lambda block: (block.bbox[1], block.bbox[0]))

    for index, block in enumerate(fused_blocks):
        block.reading_order = index

    return fused_blocks


def accept_block(block: OCRBlock) -> bool:
    text = block.text.strip()

    if not text:
        return False

    if len(text) < _MIN_BLOCK_TEXT_LENGTH:
        return False

    if block.confidence < _MIN_BLOCK_CONFIDENCE:
        return False

    if _is_only_punctuation(text):
        return False

    if _is_noise_token(text):
        return False

    return True


def _is_only_punctuation(text: str) -> bool:
    return bool(re.fullmatch(r"[^\w]+", text))


def _is_noise_token(text: str) -> bool:
    if re.fullmatch(r"[A-Z]{1,2}", text):
        return True

    if re.fullmatch(r"[0-9]{1,2}\.", text):
        return True

    if re.fullmatch(r"[Xx]{1,3}", text):
        return True

    return False


def clone_block(block: OCRBlock) -> OCRBlock:
    return OCRBlock(
        text=block.text,
        confidence=block.confidence,
        bbox=block.bbox,
        lines=list(block.lines),
        block_type=block.block_type,
        reading_order=block.reading_order,
        source=block.source,
    )


def group_overlapping_blocks(blocks: list[OCRBlock]) -> list[list[OCRBlock]]:
    remaining = sorted(blocks, key=lambda block: (block.bbox[1], block.bbox[0]))
    groups: list[list[OCRBlock]] = []

    while remaining:
        seed = remaining.pop(0)
        group = [seed]

        changed = True
        while changed:
            changed = False
            next_remaining: list[OCRBlock] = []

            for candidate in remaining:
                if belongs_to_group(candidate, group):
                    group.append(candidate)
                    changed = True
                else:
                    next_remaining.append(candidate)

            remaining = next_remaining

        groups.append(group)

    return groups


def belongs_to_group(candidate: OCRBlock, group: list[OCRBlock]) -> bool:
    for existing in group:
        if blocks_overlap(candidate, existing):
            return True

    return False


def blocks_overlap(left: OCRBlock, right: OCRBlock) -> bool:
    iou = bbox_iou(left.bbox, right.bbox)
    if iou >= 0.35:
        return True

    if bbox_contains(left.bbox, right.bbox, threshold=0.8):
        return True

    if bbox_contains(right.bbox, left.bbox, threshold=0.8):
        return True

    return False


def bbox_iou(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b

    ax2 = ax1 + aw
    ay2 = ay1 + ah
    bx2 = bx1 + bw
    by2 = by1 + bh

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    if inter_area == 0:
        return 0.0

    area_a = aw * ah
    area_b = bw * bh
    union = area_a + area_b - inter_area

    if union <= 0:
        return 0.0

    return inter_area / union


def bbox_contains(
    outer: tuple[int, int, int, int],
    inner: tuple[int, int, int, int],
    threshold: float,
) -> bool:
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner

    outer_x2 = ox + ow
    outer_y2 = oy + oh
    inner_x2 = ix + iw
    inner_y2 = iy + ih

    inter_x1 = max(ox, ix)
    inter_y1 = max(oy, iy)
    inter_x2 = min(outer_x2, inner_x2)
    inter_y2 = min(outer_y2, inner_y2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    inner_area = iw * ih
    if inner_area <= 0:
        return False

    return (inter_area / inner_area) >= threshold


def choose_best_block(group: list[OCRBlock]) -> OCRBlock:
    best = max(group, key=block_rank)
    fused = clone_block(best)

    fused.source = build_fused_source(group)

    if not fused.lines:
        rich_block = pick_richest_block(group)
        if rich_block is not None and rich_block.lines:
            fused.lines = list(rich_block.lines)

    fused.block_type = pick_block_type(group, fallback=fused.block_type)

    return fused


def block_rank(block: OCRBlock) -> tuple[float, int, int, int]:
    score = float(block.confidence)

    if block.lines:
        score += 0.15

    if block.source == "paddle_ocr" and block.confidence >= 0.75:
        score += 0.10

    text = block.text.strip()
    if len(text) > 2:
        score += 0.10

    if block.confidence < 0.25:
        score -= 0.20

    rich_score = 1 if block.lines else 0
    text_len = len(text)
    source_score = 1 if block.source == "paddle_ocr" else 0

    return (score, rich_score, text_len, source_score)


def pick_richest_block(group: list[OCRBlock]) -> OCRBlock | None:
    rich_blocks = [block for block in group if block.lines]
    if not rich_blocks:
        return None

    return max(
        rich_blocks,
        key=lambda block: (len(block.lines), block.confidence),
    )


def pick_block_type(group: list[OCRBlock], fallback: str) -> str:
    counts: dict[str, int] = {}

    for block in group:
        value = (block.block_type or "").strip()
        if not value or value == "unknown":
            continue
        counts[value] = counts.get(value, 0) + 1

    if not counts:
        return fallback

    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def build_fused_source(group: list[OCRBlock]) -> str:
    sources: list[str] = []
    seen: set[str] = set()

    for block in group:
        source = (block.source or "").strip()
        if not source:
            continue
        if source in seen:
            continue

        seen.add(source)
        sources.append(source)

    if not sources:
        return "fusion"

    if len(sources) == 1:
        return sources[0]

    return "fusion:" + ",".join(sources)

