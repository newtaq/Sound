from __future__ import annotations

import re
import unicodedata

from app.infrastructure.posters.patterns.text_patterns import (
    LEADING_NOISE_RE,
    TRAILING_NOISE_RE,
)
from app.infrastructure.posters.patterns.city_patterns import CITY_ALIASES

ICON_ONLY_LINE_RE = re.compile(r"^[^\wА-Яа-яЁёA-Za-z0-9]{1,4}\s*", re.UNICODE)


def clean_line(line: str) -> str:
    value = unicodedata.normalize("NFKC", line)
    value = value.replace("\ufeff", "")
    value = value.strip()
    value = ICON_ONLY_LINE_RE.sub("", value)
    value = LEADING_NOISE_RE.sub("", value)
    value = TRAILING_NOISE_RE.sub("", value)
    value = " ".join(value.split())
    return value.strip()


def normalize_entity_text(value: str | None) -> str:
    if not value:
        return ""

    value = clean_line(value)
    value = re.sub(r"[^\w\sА-Яа-яЁёA-Za-z0-9]", " ", value, flags=re.UNICODE)
    value = " ".join(value.split())
    return value.casefold()


def normalize_city_name(value: str | None) -> str | None:
    if not value:
        return None

    normalized = normalize_entity_text(value)
    if normalized in CITY_ALIASES:
        return CITY_ALIASES[normalized]

    cleaned = clean_line(value)
    return cleaned or None


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        normalized = normalize_entity_text(value)
        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(value.strip())

    return result

