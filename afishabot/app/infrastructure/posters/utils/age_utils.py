from __future__ import annotations

from app.infrastructure.posters.patterns.common_patterns import AGE_LIMIT_RE


def extract_age_limit(text: str | None) -> int | None:
    if not text:
        return None

    match = AGE_LIMIT_RE.search(text)
    if not match:
        return None

    try:
        return int(match.group("age"))
    except (TypeError, ValueError):
        return None
    
