from __future__ import annotations

from re import Pattern


from app.infrastructure.posters.patterns.labeled_patterns import (
    LABELED_CHAT_REGEX,
    LABELED_DATE_REGEX,
    LABELED_PRICE_REGEX,
    LABELED_TICKET_REGEX,
    LABELED_VENUE_REGEX,
)


def extract_labeled_value(
    line: str,
    regex: Pattern[str],
) -> str | None:
    if not line:
        return None

    match = regex.match(line)
    if not match:
        return None

    value = match.group("value").strip()

    if not value:
        return None

    return value


__all__ = (
    "LABELED_CHAT_REGEX",
    "LABELED_DATE_REGEX",
    "LABELED_PRICE_REGEX",
    "LABELED_TICKET_REGEX",
    "LABELED_VENUE_REGEX",
    "extract_labeled_value",
)

