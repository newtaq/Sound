from __future__ import annotations

import re

from app.infrastructure.posters.patterns.link_patterns import TICKET_LABEL_REGEX
from app.infrastructure.posters.patterns.message_patterns import (
    ENGLISH_DATE_LABEL_RE,
    ENGLISH_TICKET_LABEL_RE,
    ENGLISH_TIME_LABEL_RE,
    ENGLISH_VENUE_LABEL_RE,
)
from app.infrastructure.posters.patterns.poster_patterns import DOTTED_DATE_LINE_RE
from app.infrastructure.posters.patterns.promo_patterns import PROMO_RE
from app.infrastructure.posters.semantics.message_markers import (
    SERVICE_EXACT_VALUES,
    SOCIAL_MARKERS,
)
from app.infrastructure.posters.utils.age_utils import extract_age_limit
from app.infrastructure.posters.utils.date_utils import extract_first_date
from app.infrastructure.posters.utils.labeled_line_utils import (
    LABELED_CHAT_REGEX,
    LABELED_DATE_REGEX,
    LABELED_PRICE_REGEX,
    LABELED_TICKET_REGEX,
    LABELED_VENUE_REGEX,
    extract_labeled_value,
)
from app.infrastructure.posters.utils.price_utils import is_price_line
from app.infrastructure.posters.utils.timing_utils import extract_timings


def is_labeled_metadata_line(line: str) -> bool:
    stripped = line.strip()
    return any(
        (
            bool(extract_labeled_value(stripped, LABELED_DATE_REGEX)),
            bool(extract_labeled_value(stripped, LABELED_VENUE_REGEX)),
            bool(extract_labeled_value(stripped, LABELED_PRICE_REGEX)),
            bool(extract_labeled_value(stripped, LABELED_TICKET_REGEX)),
            bool(extract_labeled_value(stripped, LABELED_CHAT_REGEX)),
            bool(ENGLISH_DATE_LABEL_RE.match(stripped)),
            bool(ENGLISH_VENUE_LABEL_RE.match(stripped)),
            bool(ENGLISH_TIME_LABEL_RE.match(stripped)),
            bool(ENGLISH_TICKET_LABEL_RE.match(stripped)),
        )
    )


def is_non_venue_labeled_metadata_line(line: str) -> bool:
    stripped = line.strip()
    return any(
        (
            bool(extract_labeled_value(stripped, LABELED_DATE_REGEX)),
            bool(extract_labeled_value(stripped, LABELED_PRICE_REGEX)),
            bool(extract_labeled_value(stripped, LABELED_TICKET_REGEX)),
            bool(extract_labeled_value(stripped, LABELED_CHAT_REGEX)),
            bool(ENGLISH_DATE_LABEL_RE.match(stripped)),
            bool(ENGLISH_TIME_LABEL_RE.match(stripped)),
            bool(ENGLISH_TICKET_LABEL_RE.match(stripped)),
        )
    )


def is_date_like_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if extract_labeled_value(stripped, LABELED_DATE_REGEX):
        return True

    if ENGLISH_DATE_LABEL_RE.match(stripped):
        return True

    parsed_date, _ = extract_first_date(stripped)
    if parsed_date:
        return True

    if DOTTED_DATE_LINE_RE.match(stripped):
        return True

    return False


def is_time_like_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if DOTTED_DATE_LINE_RE.match(stripped):
        return False

    if ENGLISH_TIME_LABEL_RE.match(stripped):
        return True

    return bool(extract_timings(stripped))


def is_age_like_line(line: str) -> bool:
    return extract_age_limit(line) is not None


def is_ticket_like_line(line: str) -> bool:
    stripped = line.strip()
    lowered = stripped.lower()

    if ENGLISH_TICKET_LABEL_RE.match(stripped):
        return True

    if ("http://" in lowered or "https://" in lowered) and re.search(
        TICKET_LABEL_REGEX,
        lowered,
        re.IGNORECASE,
    ):
        return True

    if re.search(TICKET_LABEL_REGEX, lowered, re.IGNORECASE):
        return True

    return False


def is_promo_like_line(line: str) -> bool:
    return bool(PROMO_RE.search(line))


def is_service_line(line: str) -> bool:
    lowered = line.lower().strip()

    if not lowered:
        return True

    if lowered.startswith("#") or lowered.startswith("@"):
        return True

    if any(marker in lowered for marker in SOCIAL_MARKERS):
        if not is_ticket_like_line(lowered):
            return True

    if lowered in SERVICE_EXACT_VALUES:
        return True

    return False


def is_metadata_line(line: str) -> bool:
    return any(
        (
            is_labeled_metadata_line(line),
            is_date_like_line(line),
            is_time_like_line(line),
            is_age_like_line(line),
            is_ticket_like_line(line),
            is_promo_like_line(line),
            is_price_line(line),
        )
    )


def is_non_venue_metadata_line(line: str) -> bool:
    return any(
        (
            is_non_venue_labeled_metadata_line(line),
            is_date_like_line(line),
            is_time_like_line(line),
            is_age_like_line(line),
            is_ticket_like_line(line),
            is_promo_like_line(line),
            is_price_line(line),
        )
    )


def is_short_metadata_like_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True

    if len(stripped) > 40:
        return False

    if "http://" in stripped or "https://" in stripped:
        return False

    if "|" in stripped:
        return False

    letters_count = sum(ch.isalpha() for ch in stripped)
    words_count = len(stripped.split())

    if letters_count == 0:
        return True

    if words_count <= 1:
        return True

    if words_count <= 3 and stripped.isupper():
        return True

    return False

