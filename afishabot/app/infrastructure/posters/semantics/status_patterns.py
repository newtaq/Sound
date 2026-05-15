from __future__ import annotations

import re


CANCELLED_RE = re.compile(
    r"\b(отмен[а-я]*|cancelled?|canceled)\b",
    re.IGNORECASE,
)

POSTPONED_RE = re.compile(
    r"\b(перенос[а-я]*|перенес[а-я]*|postponed?)\b",
    re.IGNORECASE,
)

SOLD_OUT_RE = re.compile(
    r"\b(sold\s*out|soldout|солд\s*аут|билетов\s+нет|распродан[а-я]*)\b",
    re.IGNORECASE,
)

