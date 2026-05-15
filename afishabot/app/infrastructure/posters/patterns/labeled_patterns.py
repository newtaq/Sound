from __future__ import annotations

import re

from app.infrastructure.posters.utils.text_utils import build_enum_regex


DATE_LABEL_PATTERNS = (
    "дата",
    "когда",
    "when",
    "date",
)

VENUE_LABEL_PATTERNS = (
    "место",
    "площадка",
    "клуб",
    "локация",
    "venue",
    "place",
    "location",
)

PRICE_LABEL_PATTERNS = (
    "цена",
    "стоимость",
    "price",
)

TICKET_LABEL_PATTERNS = (
    "билеты",
    "билет",
    "tickets",
    "ticket",
)

CHAT_LABEL_PATTERNS = (
    "чат",
    "беседа",
    "обсуждение",
    "chat",
)

LABELED_DATE_REGEX = re.compile(
    rf"^\s*(?:{build_enum_regex(DATE_LABEL_PATTERNS)})\s*[:\-]\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

LABELED_VENUE_REGEX = re.compile(
    rf"^\s*(?:{build_enum_regex(VENUE_LABEL_PATTERNS)})\s*[:\-]\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

LABELED_PRICE_REGEX = re.compile(
    rf"^\s*(?:{build_enum_regex(PRICE_LABEL_PATTERNS)})\s*[:\-]\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

LABELED_TICKET_REGEX = re.compile(
    rf"^\s*(?:{build_enum_regex(TICKET_LABEL_PATTERNS)})\s*[:\-]\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

LABELED_CHAT_REGEX = re.compile(
    rf"^\s*(?:{build_enum_regex(CHAT_LABEL_PATTERNS)})\s*[:\-]\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

