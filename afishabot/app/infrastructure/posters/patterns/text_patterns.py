from __future__ import annotations

import re


LEADING_NOISE_RE = re.compile(r"^[^\wА-Яа-яЁёA-Za-z0-9]+", re.UNICODE)
TRAILING_NOISE_RE = re.compile(r"[^\wА-Яа-яЁёA-Za-z0-9%+]+$", re.UNICODE)

FREE_ENTRY_RE = re.compile(r"\bвход\s+свободн\w*\b|\bfree\s+entry\b", re.IGNORECASE)
DISCOUNT_RE = re.compile(r"\bскидк\w*\b|\bsale\b|\bdiscount\b", re.IGNORECASE)
PERCENT_RE = re.compile(r"\b\d{1,3}\s*%\b")

PROMO_VALUE_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_-]{3,24}$")

ARTIST_IN_TITLE_RE = re.compile(
    r"\bконцерт\s+(?P<artist>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё0-9'’._-]{1,50})\b",
    re.IGNORECASE,
)

NARRATIVE_LINE_SPLIT_RE = re.compile(r"[.!?;:]\s+")

NON_VENUE_VALUE_MARKERS = (
    "вход свободный",
    "free entry",
)

NON_DESCRIPTION_LABELS = (
    "сайт",
    "site",
    "подробнее",
    "details",
)

NON_VENUE_VALUE_RE = re.compile(
    r"(?:" + "|".join(re.escape(value) for value in NON_VENUE_VALUE_MARKERS) + r")",
    re.IGNORECASE,
)

NON_DESCRIPTION_LABEL_RE = re.compile(
    r"^(?:" + "|".join(re.escape(value) for value in NON_DESCRIPTION_LABELS) + r")$",
    re.IGNORECASE,
)

