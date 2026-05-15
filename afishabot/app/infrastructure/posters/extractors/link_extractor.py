from __future__ import annotations

import re
from enum import StrEnum

from app.domain.posters.entities.poster_draft import PosterLink
from app.domain.posters.entities.poster_input import PosterInput
from app.infrastructure.posters.patterns.link_patterns import (
    TICKET_DOMAIN_REGEX,
    TICKET_LABEL_REGEX,
)
from app.infrastructure.posters.semantics.channel_keywords import CHAT_KEYWORDS
from app.infrastructure.posters.utils.entity_normalizer import clean_line
from app.infrastructure.posters.utils.url_utils import extract_urls


class LinkType(StrEnum):
    TICKET = "ticket"
    CHAT = "chat"
    EXTERNAL = "external"


TELEGRAM_HANDLE_RE = re.compile(
    r"(?<!\w)@(?P<username>[A-Za-z0-9_]{5,32})"
)


class LinkExtractor:
    def extract(self, data: PosterInput, lines: list[str]) -> list[PosterLink]:
        seen: set[str] = set()
        result: list[PosterLink] = []

        for line in lines:
            stripped = clean_line(line)
            if not stripped:
                continue

            urls = extract_urls(stripped)
            label = self._extract_link_label_from_line(stripped)

            if urls:
                for url in urls:
                    normalized_url = self._normalize_url(url)
                    if normalized_url in seen:
                        continue

                    seen.add(normalized_url)
                    result.append(
                        PosterLink(
                            url=normalized_url,
                            label=label,
                            link_type=self._detect_link_type(label, normalized_url).value,
                        )
                    )
                continue

            handle_match = TELEGRAM_HANDLE_RE.search(stripped)
            if handle_match and self._looks_like_chat_line(stripped):
                username = handle_match.group("username")
                url = f"https://t.me/{username}"

                if url in seen:
                    continue

                seen.add(url)
                result.append(
                    PosterLink(
                        url=url,
                        label=label or f"@{username}",
                        link_type=LinkType.CHAT.value,
                    )
                )

        for button in data.buttons:
            if not button.url:
                continue

            normalized_url = self._normalize_url(button.url)
            if normalized_url in seen:
                continue

            seen.add(normalized_url)
            result.append(
                PosterLink(
                    url=normalized_url,
                    label=clean_line(button.text) if button.text else None,
                    link_type=self._detect_link_type(button.text, normalized_url).value,
                )
            )

        return result

    def _extract_link_label_from_line(self, line: str) -> str | None:
        value = line

        for url in extract_urls(line):
            value = value.replace(url, " ")

        value = TELEGRAM_HANDLE_RE.sub(" ", value)
        value = " ".join(value.split()).strip(" :|-–—\t")

        return value or None

    def _looks_like_chat_line(self, line: str) -> bool:
        lowered = line.casefold()
        return any(keyword in lowered for keyword in CHAT_KEYWORDS)

    def _detect_link_type(self, label: str | None, url: str) -> LinkType:
        lowered_label = (label or "").casefold()
        lowered_url = url.casefold()

        if "t.me/" in lowered_url or lowered_url.startswith("https://telegram.me/"):
            if any(keyword in lowered_label for keyword in CHAT_KEYWORDS):
                return LinkType.CHAT

        if lowered_label and re.search(TICKET_LABEL_REGEX, lowered_label, re.IGNORECASE):
            return LinkType.TICKET

        if re.search(TICKET_DOMAIN_REGEX, lowered_url, re.IGNORECASE):
            return LinkType.TICKET

        return LinkType.EXTERNAL

    def _normalize_url(self, url: str) -> str:
        url = url.strip()

        if url.startswith("www."):
            return f"https://{url}"

        if url.startswith("t.me/"):
            return f"https://{url}"

        if url.startswith("vk.com/"):
            return f"https://{url}"

        return url
