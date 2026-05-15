from __future__ import annotations

import re


PROMO_RE = re.compile(
    r"\b(?:промокод|promo(?:\s+code)?|код)\b",
    re.IGNORECASE,
)

PROMO_VALUE_AFTER_INTRO_RE = re.compile(
    r"""
    \b
    (?:вводи\s+)?                       
    (?:промокод|promo(?:\s+code)?|код)
    \b
    [^\S\r\n]*
    (?:[:=\-]\s*|\s+)
    (?P<code>[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_-]{2,23})
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

PROMO_FALLBACK_RE = re.compile(
    r"""
    \b
    (?:промокод|promo(?:\s+code)?|код)
    \b
    [^\n]{0,24}?
    (?:[:=\-]\s*|\s+)
    (?P<code>[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_-]{2,23})
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

