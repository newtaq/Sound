from __future__ import annotations

from app.infrastructure.posters.utils.entity_normalizer import clean_line


def choose_title(lines: list[str]) -> str | None:
    for line in lines:
        cleaned = clean_line(line)
        if cleaned:
            return cleaned
    return None

