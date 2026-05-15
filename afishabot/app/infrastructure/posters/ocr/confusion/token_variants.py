from __future__ import annotations

from app.infrastructure.posters.ocr.confusion.char_confusions import CHAR_CONFUSIONS


def generate_token_variants(value: str, limit: int = 16) -> list[str]:
    text = value.strip()
    if not text:
        return []

    seen: set[str] = set()
    variants: list[str] = []

    _add_variant(text, seen, variants)

    if len(text) <= 4 and text.isalpha():
        _generate_combinational_variants(
            text=text,
            index=0,
            current=[],
            seen=seen,
            variants=variants,
            limit=limit,
        )
        return variants[:limit]

    for index, char in enumerate(text):
        replacements = CHAR_CONFUSIONS.get(char, ())
        for replacement in replacements:
            candidate = text[:index] + replacement + text[index + 1 :]
            _add_variant(candidate, seen, variants)

            if len(variants) >= limit:
                return variants

    return variants


def _generate_combinational_variants(
    text: str,
    index: int,
    current: list[str],
    seen: set[str],
    variants: list[str],
    limit: int,
) -> None:
    if len(variants) >= limit:
        return

    if index >= len(text):
        candidate = "".join(current)
        _add_variant(candidate, seen, variants)
        return

    char = text[index]

    current.append(char)
    _generate_combinational_variants(
        text=text,
        index=index + 1,
        current=current,
        seen=seen,
        variants=variants,
        limit=limit,
    )
    current.pop()

    replacements = CHAR_CONFUSIONS.get(char, ())
    for replacement in replacements:
        current.append(replacement)
        _generate_combinational_variants(
            text=text,
            index=index + 1,
            current=current,
            seen=seen,
            variants=variants,
            limit=limit,
        )
        current.pop()

        if len(variants) >= limit:
            return


def _add_variant(value: str, seen: set[str], variants: list[str]) -> None:
    if not value:
        return

    if value in seen:
        return

    seen.add(value)
    variants.append(value)
    
