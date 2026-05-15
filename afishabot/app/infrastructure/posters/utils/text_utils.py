from __future__ import annotations

import re

from app.infrastructure.posters.patterns.common_patterns import (
    NEWLINE_RE,
    WHITESPACE_RE,
)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    value = value.replace("\xa0", " ")
    value = value.replace("\u200b", "")
    value = value.replace("\ufeff", "")

    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)

    value = re.sub(r"([A-Za-z])(\d{1,2}\s+[А-Яа-яЁё])", r"\1 \2", value)
    value = re.sub(r"([A-Za-z])(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)", r"\1 \2", value)
    value = re.sub(r"(\?[^ \n\t]*?)(\d{1,2}\s+[А-Яа-яЁё])", r"\1 \2", value)
    value = re.sub(r"(\?[^ \n\t]*?)(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)", r"\1 \2", value)

    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def split_lines(value: str | None) -> list[str]:
    if not value:
        return []

    return [line.strip() for line in value.split("\n")]


def build_enum_regex(values: tuple[str, ...]) -> str:
    if not values:
        return ""

    escaped = [re.escape(value.strip()) for value in values if value.strip()]
    return "|".join(escaped)

