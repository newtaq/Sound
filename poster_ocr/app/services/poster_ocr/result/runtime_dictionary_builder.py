from __future__ import annotations

from app.services.poster_ocr.dictionaries.runtime_dictionary import RuntimeDictionary
from app.services.poster_ocr.models import PosterOCRContext


def build_runtime_dictionary(context: PosterOCRContext) -> RuntimeDictionary:
    values: list[str] = []

    if context.description_text:
        values.extend(split_description_text(context.description_text))

    for candidate in context.entity_candidates:
        name = candidate.name.strip()
        if name:
            values.append(name)

        values.extend(
            alias.strip()
            for alias in candidate.aliases
            if alias.strip()
        )

    return RuntimeDictionary(_deduplicate_preserve_order(values))


def split_description_text(value: str) -> list[str]:
    return [
        part.strip()
        for part in value.splitlines()
        if part.strip()
    ]


def _deduplicate_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)

    return result
