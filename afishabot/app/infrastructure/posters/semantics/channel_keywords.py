from __future__ import annotations

import re


CHANNEL_PROMO_TEXT_MARKERS = (
    "концерты в ",
    "бесплатные концерты",
    "актуальный чат тура",
)

SOCIAL_URL_MARKERS = (
    "t.me/",
    "telegram.me/",
)

ORGANIZER_CHANNEL_KEYWORDS = (
    "concert",
    "promo",
    "концерт",
    "промо",
)

TOUR_KEYWORDS = (
    "тур",
    "tour",
)

CHAT_KEYWORDS = (
    "чат",
    "беседа",
)

PROMO_INTRO_KEYWORDS = (
    "промокод",
    "promo",
)

SEMANTIC_FIELD_LABELS = (
    "когда",
    "где",
    "цена",
    "билеты",
    "билет",
    "ссылка",
    "сайт",
    "подробнее",
    "беседа",
    "чат",
    "дата",
    "venue",
    "date",
    "tickets",
    "ticket",
    "site",
    "link",
)

SEMANTIC_FIELD_LABEL_RE = re.compile(
    r"^(?:" + "|".join(re.escape(value) for value in SEMANTIC_FIELD_LABELS) + r")$",
    re.IGNORECASE,
)

