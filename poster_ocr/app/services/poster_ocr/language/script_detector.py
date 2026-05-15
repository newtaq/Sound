from __future__ import annotations


CYRILLIC_RANGES = (
    ("А", "я"),
    ("Ё", "ё"),
)

LATIN_RANGES = (
    ("A", "Z"),
    ("a", "z"),
)


def detect_word_script(value: str) -> str:
    text = value.strip()
    if not text:
        return "unknown"

    cyrillic_count = 0
    latin_count = 0
    digit_count = 0

    for char in text:
        if char.isdigit():
            digit_count += 1
            continue

        if _is_cyrillic(char):
            cyrillic_count += 1
            continue

        if _is_latin(char):
            latin_count += 1
            continue

    if digit_count > 0 and cyrillic_count == 0 and latin_count == 0:
        return "numeric"

    if cyrillic_count > 0 and latin_count == 0:
        return "cyrillic"

    if latin_count > 0 and cyrillic_count == 0:
        return "latin"

    if cyrillic_count > 0 and latin_count > 0:
        return "mixed"

    return "unknown"


def _is_cyrillic(char: str) -> bool:
    for start, end in CYRILLIC_RANGES:
        if start <= char <= end:
            return True
    return False


def _is_latin(char: str) -> bool:
    for start, end in LATIN_RANGES:
        if start <= char <= end:
            return True
    return False
