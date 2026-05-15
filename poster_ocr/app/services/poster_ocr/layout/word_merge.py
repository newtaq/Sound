from __future__ import annotations

from app.services.poster_ocr.models import OCRLine, OCRWord


def merge_line_words(line: OCRLine) -> str:
    words = _sorted_words(line.words)
    if not words:
        return line.text.strip()

    parts: list[str] = [words[0].text.strip()]

    for previous_word, current_word in zip(words, words[1:]):
        current_text = current_word.text.strip()
        if not current_text:
            continue

        gap = _horizontal_gap(previous_word, current_word)

        if _should_merge(previous_word, current_word, gap):
            parts[-1] += current_text
        else:
            parts.append(current_text)

    return " ".join(part for part in parts if part)


def merge_block_lines(lines: list[OCRLine]) -> str:
    parts = [merge_line_words(line) for line in lines]
    parts = [part for part in parts if part.strip()]
    return "\n".join(parts)


def _sorted_words(words: list[OCRWord]) -> list[OCRWord]:
    return sorted(words, key=lambda word: (word.bbox[0], word.bbox[1]))


def _horizontal_gap(left_word: OCRWord, right_word: OCRWord) -> int:
    left_x, _, left_w, _ = left_word.bbox
    right_x, _, _, _ = right_word.bbox
    return right_x - (left_x + left_w)


def _should_merge(left_word: OCRWord, right_word: OCRWord, gap: int) -> bool:
    if gap < 0:
        return False

    left_text = left_word.text.strip()
    right_text = right_word.text.strip()

    if not left_text or not right_text:
        return False

    if gap <= 6:
        return True

    if len(left_text) == 1 and len(right_text) == 1 and gap <= 28:
        return True

    if len(left_text) <= 2 and len(right_text) <= 2 and gap <= 18:
        return True

    return False
