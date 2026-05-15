from __future__ import annotations

import re

from app.infrastructure.posters.patterns.promo_patterns import (
    PROMO_FALLBACK_RE,
    PROMO_VALUE_AFTER_INTRO_RE,
)


def extract_promo_codes(text: str | None) -> list[str]:
    if not text:
        return []

    text = text.strip()
    if not text:
        return []

    result: list[str] = []
    seen: set[str] = set()

    banned_values = {
        "промокод",
        "promo",
        "code",
        "код",
        "билеты",
        "билет",
        "скидка",
        "скидкой",
        "sale",
        "discount",
        "ticket",
        "tickets",
        "bosspromotion",
        "vk",
        "youtube",
        "youtu",
        "wall",
        "join",
        "http",
        "https",
        "www",
    }

    def add_code(value: str) -> None:
        code = value.strip(" \t\n\r.,:;!?()[]{}<>\"'`“”‘’|/-_")
        if not code:
            return

        lowered = code.casefold()

        if lowered in banned_values:
            return

        if code.isdigit():
            return

        if len(code) < 3 or len(code) > 24:
            return

        if "://" in code:
            return

        if "/" in code or "\\" in code:
            return

        if "." in code:
            return

        if "@" in code:
            return

        if lowered.startswith(("http", "www")):
            return

        if lowered.startswith(("vk", "youtu", "t.me", "telegram")):
            return

        if re.fullmatch(r"-?\d[\d_-]*", code):
            return

        if not re.fullmatch(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_-]{1,23}", code):
            return

        key = lowered
        if key in seen:
            return

        seen.add(key)
        result.append(code)

    for match in PROMO_VALUE_AFTER_INTRO_RE.finditer(text):
        add_code(match.group("code"))

    if result:
        return result

    for match in PROMO_FALLBACK_RE.finditer(text):
        add_code(match.group("code"))

    return result

