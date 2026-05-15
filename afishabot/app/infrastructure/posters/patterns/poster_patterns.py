from __future__ import annotations

import re

SERVICE_LINE_PREFIXES = (
    "#",
    "@",
)

DESCRIPTION_BLOCK_PREFIXES = (
    "цена:",
    "стоимость:",
    "билеты:",
    "ticket:",
    "tickets:",
    "venue:",
    "где:",
    "когда:",
    "date:",
    "doors:",
    "start:",
    "возраст:",
    "age:",
)

DOTTED_DATE_LINE_RE = re.compile(
    r"^\d{1,2}\.\d{1,2}(?:\.\d{2,4})?\b",
)

TIME_ONLY_RE = re.compile(
    r"\b\d{1,2}:\d{2}\b",
)

TIME_RANGE_RE = re.compile(
    r"\b\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\b",
)

INLINE_VENUE_RE = re.compile(
    r"""
    \b
    (?:в|на)
    \s+
    (?:
        клубе|клуб|площадке|venue|hall|bar|stage|арене|arena
    )?
    \s*
    (?P<venue>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё0-9&'"().\- ]{1,40})
    """,
    re.IGNORECASE | re.VERBOSE,
)

