from __future__ import annotations

import re

from app.domain.posters.entities.poster_draft import PosterOccurrenceDraft

from app.infrastructure.posters.classifiers.line_classification import (
    is_age_like_line,
    is_labeled_metadata_line,
    is_non_venue_metadata_line,
    is_price_line,
    is_promo_like_line,
    is_short_metadata_like_line,
    is_ticket_like_line,
    is_time_like_line,
)

from app.infrastructure.posters.patterns.text_patterns import (
    DISCOUNT_RE,
    FREE_ENTRY_RE,
    NARRATIVE_LINE_SPLIT_RE,
    NON_DESCRIPTION_LABEL_RE,
    PROMO_VALUE_RE,
)

from app.infrastructure.posters.semantics.channel_keywords import (
    CHANNEL_PROMO_TEXT_MARKERS,
    SOCIAL_URL_MARKERS,
    SEMANTIC_FIELD_LABEL_RE,
)

from app.infrastructure.posters.utils.entity_normalizer import (
    clean_line,
    normalize_entity_text,
)

from app.infrastructure.posters.utils.url_utils import extract_urls


ARTIST_SPLIT_SEPARATORS = ("|", ",", " / ", " • ", " & ")

DESCRIPTION_LINK_LABEL_SKIP_WORDS = (
    "site",
    "сайт",
    "подробнее",
    "details",
)

DESCRIPTION_BLOCK_PREFIXES = (
    "в программе",
    "line up",
    "поддержка",
    "special guest",
)

NARRATIVE_MIN_WORDS = 8
NARRATIVE_MIN_LETTERS = 25
NARRATIVE_ALT_MIN_PARTS = 2
NARRATIVE_ALT_MIN_LETTERS = 20


class DescriptionExtractor:
    def extract(
        self,
        lines: list[str],
        title: str | None,
        artist_names: list[str],
        occurrences: list[PosterOccurrenceDraft],
        promo_codes: list[str],
    ) -> str | None:
        if not lines:
            return None

        excluded_lines = self._build_excluded_description_lines(
            title=title,
            artist_names=artist_names,
            occurrences=occurrences,
            promo_codes=promo_codes,
        )

        result_lines: list[str] = []
        promo_code_set = {
            normalize_entity_text(value)
            for value in promo_codes
            if value.strip()
        }

        for line in lines:
            stripped = clean_line(line)
            if not stripped:
                continue

            normalized = normalize_entity_text(stripped)
            if not normalized:
                continue

            if normalized in excluded_lines:
                continue

            if self._is_artist_block_line(stripped, artist_names):
                continue

            if self._looks_like_narrative_line(stripped):
                result_lines.append(stripped)
                continue

            if is_labeled_metadata_line(stripped):
                continue

            if is_non_venue_metadata_line(stripped):
                continue

            if is_time_like_line(stripped):
                continue

            if is_age_like_line(stripped):
                continue

            if is_ticket_like_line(stripped):
                continue

            if is_price_line(stripped):
                continue

            if is_promo_like_line(stripped):
                continue

            if self._looks_like_channel_promo_line(stripped):
                continue

            if self._looks_like_promo_code_value(stripped, promo_code_set):
                continue

            if self._looks_like_age_value(stripped):
                continue

            lowered = stripped.casefold()
            if any(lowered.startswith(prefix) for prefix in DESCRIPTION_BLOCK_PREFIXES):
                continue

            if (
                is_short_metadata_like_line(stripped)
                and not self._looks_like_meaningful_short_sentence(stripped)
            ):
                continue

            if extract_urls(stripped):
                label = self._extract_link_label_from_line(stripped) or ""
                if self._looks_like_non_description_link_label(label):
                    continue

            if DISCOUNT_RE.search(stripped) and not self._looks_like_narrative_line(stripped):
                continue

            if FREE_ENTRY_RE.search(stripped):
                continue

            result_lines.append(stripped)

        result = "\n".join(result_lines).strip()
        return result or None

    def _build_excluded_description_lines(
        self,
        title: str | None,
        artist_names: list[str],
        occurrences: list[PosterOccurrenceDraft],
        promo_codes: list[str],
    ) -> set[str]:
        excluded: set[str] = set()

        if title:
            excluded.add(normalize_entity_text(title))

        for artist_name in artist_names:
            if artist_name and artist_name.strip():
                excluded.add(normalize_entity_text(artist_name))

        for promo_code in promo_codes:
            if promo_code and promo_code.strip():
                excluded.add(normalize_entity_text(promo_code))

        for occurrence in occurrences:
            for value in (
                occurrence.city_name,
                occurrence.venue_name,
                occurrence.address,
                occurrence.raw_date_text,
                occurrence.raw_line,
            ):
                if value and value.strip():
                    excluded.add(normalize_entity_text(value))

        excluded.discard("")
        return excluded

    def _looks_like_promo_code_value(self, line: str, promo_code_set: set[str]) -> bool:
        normalized = normalize_entity_text(line)
        if not normalized:
            return False

        if normalized in promo_code_set:
            return True

        if PROMO_VALUE_RE.match(line) and normalized.isascii():
            return True

        if PROMO_VALUE_RE.match(line) and line.isupper():
            return True

        return False

    def _looks_like_non_description_link_label(self, value: str) -> bool:
        cleaned = clean_line(value)
        if not cleaned:
            return False

        normalized = normalize_entity_text(cleaned)
        if not normalized:
            return False

        if normalized in DESCRIPTION_LINK_LABEL_SKIP_WORDS:
            return True

        return bool(NON_DESCRIPTION_LABEL_RE.match(normalized))

    def _looks_like_age_value(self, line: str) -> bool:
        return bool(re.fullmatch(r"\d{1,2}\+?", line.strip()))

    def _looks_like_meaningful_short_sentence(self, line: str) -> bool:
        if len(line) > 40:
            return True

        words = line.split()
        return len(words) >= 4

    def _looks_like_channel_promo_line(self, line: str) -> bool:
        lowered = line.casefold()

        if not any(marker in lowered for marker in SOCIAL_URL_MARKERS):
            return False

        return any(marker in lowered for marker in CHANNEL_PROMO_TEXT_MARKERS)

    def _looks_like_narrative_line(self, line: str) -> bool:
        if not line:
            return False

        if extract_urls(line):
            return False

        if is_labeled_metadata_line(line):
            return False

        if is_ticket_like_line(line):
            return False

        if self._looks_like_channel_promo_line(line):
            return False

        cleaned = clean_line(line)
        words = cleaned.split()
        letters_count = sum(ch.isalpha() for ch in cleaned)

        if len(words) >= NARRATIVE_MIN_WORDS and letters_count >= NARRATIVE_MIN_LETTERS:
            return True

        sentence_parts = [
            part.strip()
            for part in NARRATIVE_LINE_SPLIT_RE.split(cleaned)
            if part.strip()
        ]
        if (
            len(sentence_parts) >= NARRATIVE_ALT_MIN_PARTS
            and letters_count >= NARRATIVE_ALT_MIN_LETTERS
        ):
            return True

        return False

    def _looks_like_semantic_field_label(self, value: str) -> bool:
        cleaned = clean_line(value)
        if not cleaned:
            return False

        normalized = normalize_entity_text(cleaned)
        if not normalized:
            return False

        return bool(SEMANTIC_FIELD_LABEL_RE.match(normalized))

    def _is_artist_block_line(self, line: str, artist_names: list[str]) -> bool:
        if not artist_names:
            return False

        if not any(separator in line for separator in ARTIST_SPLIT_SEPARATORS):
            return False

        known = {
            normalize_entity_text(name)
            for name in artist_names
            if name.strip()
        }
        if not known:
            return False

        parts = self._split_artist_candidate(line)
        normalized_parts = []

        for part in parts:
            normalized_part = normalize_entity_text(part)
            if normalized_part:
                normalized_parts.append(normalized_part)

        if not normalized_parts:
            return False

        return all(part in known for part in normalized_parts)

    def _split_artist_candidate(self, value: str) -> list[str]:
        for separator in ARTIST_SPLIT_SEPARATORS:
            if separator in value:
                return [part.strip() for part in value.split(separator)]
        return [value]

    def _extract_link_label_from_line(self, line: str) -> str | None:
        value = line
        for url in extract_urls(line):
            value = value.replace(url, " ")

        value = " ".join(value.split()).strip(" :|-–—\t")
        return value or None
    
