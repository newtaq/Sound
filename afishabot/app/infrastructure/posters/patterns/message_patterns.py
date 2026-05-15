from __future__ import annotations

import re


ENGLISH_DATE_LABEL_RE = re.compile(
    r"^\s*date\s*:\s*.+$",
    re.IGNORECASE,
)

ENGLISH_VENUE_LABEL_RE = re.compile(
    r"^\s*venue\s*:\s*.+$",
    re.IGNORECASE,
)

ENGLISH_TIME_LABEL_RE = re.compile(
    r"^\s*(doors|door|start|show|time)\s*:\s*.+$",
    re.IGNORECASE,
)

ENGLISH_TICKET_LABEL_RE = re.compile(
    r"^\s*(ticket|tickets)\s*:\s*.+$",
    re.IGNORECASE,
)

