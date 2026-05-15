from __future__ import annotations

from urllib.parse import urlparse

from app.infrastructure.posters.patterns.link_patterns import URL_RE


def extract_urls(value: str | None) -> list[str]:
    if not value:
        return []

    result: list[str] = []
    seen: set[str] = set()

    for match in URL_RE.finditer(value):
        url = match.group(1).strip(".,;:!?)]>}\"'")

        if not url:
            continue

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        parsed = urlparse(url)
        if not parsed.netloc:
            continue

        normalized = url.rstrip("/")

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(normalized)

    return result

