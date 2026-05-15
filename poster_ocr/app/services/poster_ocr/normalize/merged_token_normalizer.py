from __future__ import annotations

from app.services.poster_ocr.confusion.token_variants import generate_token_variants
from app.services.poster_ocr.language.script_detector import detect_word_script


def normalize_merged_token(value: str) -> str:
    text = value.strip()
    if not text:
        return ""

    if _should_keep_original(text):
        return text

    variants = generate_token_variants(text, limit=16)
    if not variants:
        return text

    best_variant = text
    best_score = _score_variant(text)

    for variant in variants:
        if not _is_alpha_like(variant):
            continue

        score = _score_variant(variant)
        if score > best_score:
            best_variant = variant
            best_score = score

    return best_variant


def _should_keep_original(value: str) -> bool:
    if any(char.isdigit() for char in value):
        return True

    if any(char in ".:+/-<>" for char in value):
        return True

    if len(value) > 4:
        return True

    return False


def _is_alpha_like(value: str) -> bool:
    return bool(value) and all(char.isalpha() for char in value)


def _score_variant(value: str) -> tuple[int, int, int]:
    script = detect_word_script(value)

    script_score = 0
    if script == "cyrillic":
        script_score = 4
    elif script == "latin":
        script_score = 3
    elif script == "mixed":
        script_score = -10

    cyrillic_count = sum(1 for char in value if _is_cyrillic(char))
    latin_count = sum(1 for char in value if _is_latin(char))

    short_cyr_bonus = 0
    if cyrillic_count > 0 and latin_count == 0:
        short_cyr_bonus = 2

    return (
        script_score,
        short_cyr_bonus,
        max(cyrillic_count, latin_count),
    )


def _is_cyrillic(char: str) -> bool:
    return ("А" <= char <= "я") or char in {"Ё", "ё"}


def _is_latin(char: str) -> bool:
    return ("A" <= char <= "Z") or ("a" <= char <= "z")
