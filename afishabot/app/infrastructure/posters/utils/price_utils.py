from __future__ import annotations

import re


PRICE_KEYWORDS = (
    "руб",
    "₽",
    "р",
    "цена",
    "стоимость",
    "от",
)

PRICE_REGEX = re.compile(
    r"\d+\s*(?:руб|₽|р)",
    re.IGNORECASE,
)


def is_price_line(line: str) -> bool:
    lowered = line.lower()

    for keyword in PRICE_KEYWORDS:
        if keyword in lowered:
            return True

    if PRICE_REGEX.search(line):
        return True

    return False

