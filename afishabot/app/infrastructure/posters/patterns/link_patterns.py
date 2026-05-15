from __future__ import annotations

import re 

from app.infrastructure.posters.utils.text_utils import build_enum_regex


TICKET_LABEL_PATTERNS = (
    "билет",
    "купить",
    "tickets",
    "ticket",
    "регистрация",
    "register",
)

TICKET_DOMAIN_PATTERNS = (
    "qtickets",
    "ticketcloud",
    "ticketscloud",
    "radario",
    "iframeab",
    "kassir",
    "ponominalu",
    "concert",
    "afisha",
    "event",
)


TICKET_LABEL_REGEX = build_enum_regex(TICKET_LABEL_PATTERNS)

TICKET_DOMAIN_REGEX = build_enum_regex(TICKET_DOMAIN_PATTERNS)

URL_RE = re.compile(
    r"""
    (?P<url>
        (?:
            https?://
            |
            www\.
            |
            t\.me/
            |
            vk\.com/
        )
        [^\s<>()]+
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

URL_REGEX = URL_RE

