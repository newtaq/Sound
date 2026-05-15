from __future__ import annotations

import re


MULTIPLE_SPACES_RE = re.compile(r"\s+")
DASH_VARIANTS_RE = re.compile(r"[–—−]")
QUOTE_VARIANTS_RE = re.compile(r"[«»„“”]")


def normalize_line(line: str) -> str:
    if not line:
        return ""

    value = line.strip()

    value = DASH_VARIANTS_RE.sub("-", value)
    value = QUOTE_VARIANTS_RE.sub('"', value)

    value = MULTIPLE_SPACES_RE.sub(" ", value)

    return value.strip()


def normalize_lines(lines: list[str]) -> list[str]:
    result: list[str] = []

    for line in lines:
        normalized = normalize_line(line)

        if not normalized:
            continue

        result.append(normalized)

    return result
