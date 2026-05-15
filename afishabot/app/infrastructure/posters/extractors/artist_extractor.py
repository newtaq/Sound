from __future__ import annotations

import re 

from app.infrastructure.posters.classifiers.line_classification import (
    is_date_like_line,
    is_metadata_line,
    is_price_line,
    is_service_line,
    is_ticket_like_line,
)

from app.infrastructure.posters.patterns.poster_patterns import (
    DOTTED_DATE_LINE_RE,
)

from app.infrastructure.posters.patterns.text_patterns import (
    ARTIST_IN_TITLE_RE,
)

from app.infrastructure.posters.semantics.semantic_markers import (
    NON_ARTIST_EXACT_VALUES,
    NON_CITY_EXACT_VALUES,
)

from app.infrastructure.posters.utils.entity_normalizer import (
    clean_line,
    normalize_entity_text,
    unique_preserve_order,
)

from app.infrastructure.posters.utils.url_utils import extract_urls


ARTIST_SPLIT_SEPARATORS = ("|", ",", " / ", " • ", " & ")
TITLE_MAX_WORDS_FOR_ARTIST_FALLBACK = 5
ARTIST_BLOCK_SCAN_LINES = 6
MAX_ARTIST_LINE_LENGTH = 140
MAX_ARTIST_NAME_LENGTH = 80
MIN_ARTIST_NAME_LENGTH = 2

ARTIST_STOP_WORDS = {
    "окей",
    "надо",
    "ждем",
    "ждём",
    "сегодня",
    "завтра",
    "послезавтра",
    "слушать",
    "скачать",
    "билеты",
    "билет",
    "концерт",
    "тур",
    "розыгрыш",
    "подробнее",
    "заходите",
    "комментарии",
    "комменты",
    "чат",
    "ссылка",
    "репост",
    "группа",
    "профиль",
    "бесплатно",
    "скидка",
    "промокод",
    "boss",
}

ARTIST_BAD_EXACT_VALUES = {
    "или",
    "да",
    "нет",
    "хорошо",
    "красава",
    "мясо",
    "огни",
    "лето",
    "быть всем",
}

HANDLE_RE = re.compile(r"^@[A-Za-z0-9_]{3,}$")
ONLY_NOISE_RE = re.compile(r"^[^A-Za-zА-Яа-яЁё0-9]+$")
LOWER_HANDLE_LIKE_RE = re.compile(r"^[a-z0-9_]{3,}$")
SERVICE_PREFIX_RE = re.compile(
    r"^(слушать|скачать|билеты|подробнее|ссылка|чат|комменты?)\b",
    re.IGNORECASE,
)


class ArtistExtractor:
    def extract(self, lines: list[str], title: str | None) -> list[str]:
        if not lines:
            return []

        title_norm = normalize_entity_text(title)
        artist_block: list[str] = []

        for index, line in enumerate(lines[:ARTIST_BLOCK_SCAN_LINES]):
            stripped = clean_line(line)
            if not stripped:
                continue

            if index == 0:
                continue

            if normalize_entity_text(stripped) == title_norm:
                continue

            if self._is_obvious_artist_block_stop(stripped):
                break

            if self._is_artist_candidate_line(stripped):
                artist_block.append(stripped)
                continue

            if artist_block:
                break

        result: list[str] = []

        for value in artist_block:
            for part in self._split_artist_candidate(value):
                cleaned = clean_line(part)
                if not cleaned:
                    continue

                if not self._is_artist_name(cleaned):
                    continue

                if normalize_entity_text(cleaned) == title_norm:
                    continue

                result.append(cleaned)

        if result:
            return unique_preserve_order(result)

        title_artist = self._extract_artist_from_title(title)
        if title_artist:
            return [title_artist]

        return []

    def _extract_artist_from_title(self, title: str | None) -> str | None:
        if not title:
            return None

        cleaned = clean_line(title)
        if not cleaned:
            return None

        if len(cleaned.split()) > TITLE_MAX_WORDS_FOR_ARTIST_FALLBACK:
            return None

        match = ARTIST_IN_TITLE_RE.search(cleaned)
        if not match:
            return None

        artist = clean_line(match.group("artist"))
        return artist or None

    def _is_artist_candidate_line(self, line: str) -> bool:
        normalized = normalize_entity_text(line)

        if not normalized:
            return False

        if is_metadata_line(line):
            return False

        if is_service_line(line):
            return False

        if is_price_line(line):
            return False

        if DOTTED_DATE_LINE_RE.match(line):
            return False

        if normalized in NON_ARTIST_EXACT_VALUES:
            return False

        if len(line) > MAX_ARTIST_LINE_LENGTH:
            return False

        return True

    def _is_artist_name(self, value: str) -> bool:
        cleaned = clean_line(value)
        if not cleaned:
            return False

        normalized = normalize_entity_text(cleaned)
        if not normalized:
            return False

        if ONLY_NOISE_RE.match(cleaned):
            return False

        if HANDLE_RE.match(cleaned):
            return False

        if cleaned.startswith("@"):
            return False

        if extract_urls(cleaned):
            return False

        if SERVICE_PREFIX_RE.match(cleaned):
            return False

        if normalized in ARTIST_STOP_WORDS:
            return False

        if normalized in ARTIST_BAD_EXACT_VALUES:
            return False

        if LOWER_HANDLE_LIKE_RE.match(cleaned):
            return False

        if normalized.isdigit():
            return False

        if len(cleaned) < 2 or len(cleaned) > 60:
            return False

        words = cleaned.split()
        if len(words) > 5:
            return False

        letters_count = sum(ch.isalpha() for ch in cleaned)
        if letters_count == 0:
            return False

        if all(word.casefold() in ARTIST_STOP_WORDS for word in words):
            return False

        return True

    def _split_artist_candidate(self, value: str) -> list[str]:
        for separator in ARTIST_SPLIT_SEPARATORS:
            if separator in value:
                return [part.strip() for part in value.split(separator)]
        return [value]

    def _is_obvious_artist_block_stop(self, line: str) -> bool:
        if is_date_like_line(line):
            return True

        if is_metadata_line(line):
            return True

        if is_ticket_like_line(line):
            return True

        if normalize_entity_text(line) in NON_CITY_EXACT_VALUES:
            return True

        return False
    
