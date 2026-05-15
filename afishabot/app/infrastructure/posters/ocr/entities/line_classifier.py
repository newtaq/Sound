from __future__ import annotations

import re

from app.infrastructure.posters.ocr.entities.entity_name_matcher import find_best_entity_name_match
from app.infrastructure.posters.ocr.models import PosterOCRContext


DATE_RE = re.compile(r"^\d{1,2}\.\d{1,2}$")
AGE_RE = re.compile(r"^\d{1,2}\+$")


def classify_normalized_block_text(
    text: str,
    context: PosterOCRContext,
) -> str:
    value = text.strip()
    if not value:
        return "unknown"

    if AGE_RE.fullmatch(value):
        return "age"

    if DATE_RE.fullmatch(value):
        return "date"

    exact_match = _find_exact_match(value, context)
    if exact_match is not None:
        return exact_match

    fuzzy_match = find_best_entity_name_match(
        text=value,
        context=context,
        entity_types=("venue", "city", "artist"),
        threshold=0.74,
    )
    if fuzzy_match is not None:
        return fuzzy_match.candidate.entity_type

    return "unknown"


def resolve_normalized_block_text(
    text: str,
    context: PosterOCRContext,
) -> str:
    value = text.strip()
    if not value:
        return ""

    if AGE_RE.fullmatch(value) or DATE_RE.fullmatch(value):
        return value

    fuzzy_match = find_best_entity_name_match(
        text=value,
        context=context,
        entity_types=("venue", "city", "artist"),
        threshold=0.80,
    )
    if fuzzy_match is not None:
        return fuzzy_match.candidate.name

    return value


def _find_exact_match(
    text: str,
    context: PosterOCRContext,
) -> str | None:
    normalized_text = _normalize(text)

    for candidate in context.entity_candidates:
        for raw_value in _iter_candidate_values(candidate):
            if _normalize(raw_value) == normalized_text:
                return candidate.entity_type

    return None


def _iter_candidate_values(candidate) -> list[str]:
    values: list[str] = []

    name = candidate.name.strip()
    if name:
        values.append(name)

    for alias in candidate.aliases:
        alias_value = alias.strip()
        if alias_value:
            values.append(alias_value)

    return values


def _normalize(value: str) -> str:
    return "".join(value.lower().split())

