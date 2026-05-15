from __future__ import annotations

import re


CITY_ALIASES = {
    "питер": "Санкт-Петербург",
    "спб": "Санкт-Петербург",
    "санкт петербург": "Санкт-Петербург",
    "санкт-петербург": "Санкт-Петербург",
    "москва": "Москва",
    "минск": "Минск",
}

CITY_HINT_KEYWORDS = tuple(CITY_ALIASES.keys())

CITY_HINT_RE = re.compile(
    r"\b(" + "|".join(re.escape(value) for value in CITY_HINT_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

CITY_ALIAS_RE = re.compile(
    r"\b(" + "|".join(re.escape(value) for value in CITY_ALIASES.keys()) + r")\b",
    re.IGNORECASE,
)

TOUR_CITY_LINK_RE = re.compile(
    r"^(?P<city>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё\- ]{1,50})\s*[:\-–—]\s*(?P<rest>.+)$"
)

NON_CITY_VALUE_MARKERS = (
    "вход свободный",
    "free entry",
)

NON_CITY_VALUE_RE = re.compile(
    r"(?:" + "|".join(re.escape(value) for value in NON_CITY_VALUE_MARKERS) + r")",
    re.IGNORECASE,
)

