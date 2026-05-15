from __future__ import annotations

import re
from datetime import date, datetime

from app.domain.posters.entities.poster_draft import (
    PosterLink,
    PosterOccurrenceDraft,
)
from app.domain.posters.enums import DateSource
from app.infrastructure.posters.classifiers.line_classification import (
    is_date_like_line,
    is_metadata_line,
    is_non_venue_metadata_line,
    is_price_line,
    is_service_line,
    is_ticket_like_line,
)
from app.infrastructure.posters.models.date_result import DateResult
from app.infrastructure.posters.patterns.city_patterns import (
    CITY_ALIAS_RE,
    CITY_HINT_RE,
    NON_CITY_VALUE_RE,
)
from app.infrastructure.posters.patterns.date_patterns import (
    DOTTED_DATE_ANY_RE,
    ENGLISH_DATE_RE,
    ENGLISH_MONTHS,
    INLINE_CITY_DATE_RE,
    MULTICITY_DATE_CITY_RE,
    PIPE_OCCURRENCE_RE,
)
from app.infrastructure.posters.patterns.poster_patterns import (
    DOTTED_DATE_LINE_RE,
    INLINE_VENUE_RE,
)
from app.infrastructure.posters.patterns.text_patterns import (
    NON_VENUE_VALUE_RE,
)
from app.infrastructure.posters.semantics.channel_keywords import (
    SEMANTIC_FIELD_LABEL_RE,
)
from app.infrastructure.posters.semantics.semantic_markers import (
    NON_CITY_EXACT_VALUES,
)
from app.infrastructure.posters.utils.date_utils import extract_date_range
from app.infrastructure.posters.utils.entity_normalizer import (
    clean_line,
    normalize_city_name,
    normalize_entity_text,
)
from app.infrastructure.posters.utils.labeled_line_utils import (
    LABELED_DATE_REGEX,
    LABELED_VENUE_REGEX,
    extract_labeled_value,
)
from app.infrastructure.posters.utils.timing_utils import extract_timings
from app.infrastructure.posters.utils.url_utils import extract_urls


class LinkType:
    TICKET = "ticket"
    CHAT = "chat"
    EXTERNAL = "external"


CITY_LINK_SEPARATORS = (":", " - ", " — ", " – ")

VENUE_HINT_WORDS = (
    "club",
    "hall",
    "place",
    "roof",
    "stage",
    "arena",
    "base",
    "stadium",
    "loft",
    "бар",
    "клуб",
    "дворец",
    "арена",
    "площадка",
    "сцена",
)

CITY_LABEL_MAX_WORDS = 3
MAX_CITY_LINE_LENGTH = 40
MAX_VENUE_LINE_LENGTH = 60

INLINE_DATE_CITY_RE = re.compile(
    r"^(?P<date>\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)\s+(?P<city>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё\- ]{1,60})$"
)

CITY_IN_SENTENCE_RE = re.compile(
    r"\b(?:в|во|in)\s+(?P<city>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё\-]{1,40}(?:\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё\-]{1,40}){0,2})\b"
)

BAD_CITY_VALUES = {
    "https",
    "http",
    "www",
    "vk",
    "youtu",
    "youtube",
    "t",
    "me",
    "join",
    "wall",
    "music",
    "video",
    "channel",
    "boss",
    "ticket",
    "tickets",
    "билеты",
    "билетики",
    "promo",
    "promocode",
    "промокод",
}


class OccurrenceExtractor:
    def extract(
        self,
        lines: list[str],
        title: str | None,
        artist_names: list[str],
        published_at: datetime | None,
        links: list[PosterLink],
    ) -> list[PosterOccurrenceDraft]:
        multicity_from_links = self._extract_multicity_occurrences_from_links(links)
        if len(multicity_from_links) >= 2:
            return multicity_from_links

        multicity = self._extract_multicity_occurrences(
            lines=lines,
            published_at=published_at,
            links=links,
        )
        if multicity:
            return multicity

        occurrence = self._extract_single_occurrence(
            lines=lines,
            title=title,
            artist_names=artist_names,
            published_at=published_at,
        )
        return [occurrence] if occurrence else []

    def _extract_multicity_occurrences(
        self,
        lines: list[str],
        published_at: datetime | None,
        links: list[PosterLink],
    ) -> list[PosterOccurrenceDraft]:
        result: list[PosterOccurrenceDraft] = []
        seen: set[tuple[str, date | None]] = set()

        def add_occurrence(
            city_name: str | None,
            event_date: date | None = None,
            raw_date_text: str | None = None,
            raw_line: str | None = None,
            venue_name: str | None = None,
            timings: list | None = None,
        ) -> None:
            normalized_city = normalize_entity_text(city_name)
            normalized_venue = normalize_entity_text(venue_name)
            key_base = normalized_city or normalized_venue

            if not key_base:
                return

            if normalized_city and not self._is_safe_city_candidate(city_name):
                city_name = None
                normalized_city = ""

            if not normalized_city and not normalized_venue:
                return

            key = ((normalized_city or normalized_venue), event_date)
            if key in seen:
                return

            seen.add(key)
            result.append(
                PosterOccurrenceDraft(
                    city_name=city_name,
                    venue_name=venue_name,
                    event_date=event_date,
                    timings=timings or [],
                    raw_date_text=raw_date_text,
                    raw_line=raw_line,
                )
            )

        for line in lines:
            raw_line = clean_line(line)
            parsed_line = self._prepare_line_for_parsing(line)

            if not raw_line or not parsed_line:
                continue

            date_city_match = MULTICITY_DATE_CITY_RE.match(parsed_line)
            if date_city_match:
                date_result = self._parse_date_result(
                    text=date_city_match.group("date"),
                    published_at=published_at,
                )
                city = self._normalize_safe_city(date_city_match.group("city"))
                add_occurrence(
                    city_name=city,
                    event_date=date_result.start_date if date_result else None,
                    raw_date_text=date_result.raw_text if date_result else None,
                    raw_line=raw_line,
                )
                continue

            inline_date_city_match = INLINE_DATE_CITY_RE.match(parsed_line)
            if inline_date_city_match:
                date_result = self._parse_date_result(
                    text=inline_date_city_match.group("date"),
                    published_at=published_at,
                )
                city = self._normalize_safe_city(inline_date_city_match.group("city"))
                add_occurrence(
                    city_name=city,
                    event_date=date_result.start_date if date_result else None,
                    raw_date_text=date_result.raw_text if date_result else None,
                    raw_line=raw_line,
                )
                continue

            pipe_match = PIPE_OCCURRENCE_RE.match(parsed_line)
            if pipe_match:
                date_result = self._parse_date_result(
                    text=pipe_match.group("date"),
                    published_at=published_at,
                )
                venue, city = self._split_venue_and_city(pipe_match.group("venue_city"))
                if city:
                    city = self._normalize_safe_city(city)

                timings = self._deduplicate_timings(
                    extract_timings(pipe_match.group("times"))
                )

                add_occurrence(
                    city_name=city,
                    venue_name=venue,
                    event_date=date_result.start_date if date_result else None,
                    raw_date_text=date_result.raw_text if date_result else None,
                    timings=timings,
                    raw_line=raw_line,
                )
                continue

            city, _ = self._extract_city_link_candidate(raw_line)
            if city:
                add_occurrence(
                    city_name=city,
                    raw_line=raw_line,
                )

        for item in self._extract_multicity_occurrences_from_links(links):
            add_occurrence(
                city_name=item.city_name,
                event_date=item.event_date,
                raw_date_text=item.raw_date_text,
                raw_line=item.raw_line,
                venue_name=item.venue_name,
                timings=item.timings,
            )

        return result

    def _extract_multicity_occurrences_from_links(
        self,
        links: list[PosterLink],
    ) -> list[PosterOccurrenceDraft]:
        result: list[PosterOccurrenceDraft] = []
        seen: set[str] = set()

        for link in links:
            if link.link_type != LinkType.TICKET:
                continue

            label = clean_line(link.label or "")
            if not label:
                continue

            if self._is_url_like_value(label):
                continue

            if self._looks_like_semantic_field_label(label):
                continue

            if NON_CITY_VALUE_RE.search(label):
                continue

            if is_metadata_line(label):
                continue

            if extract_urls(label):
                continue

            words_count = len(label.split())
            if words_count < 1 or words_count > CITY_LABEL_MAX_WORDS:
                continue

            if not (label[:1].isupper() or CITY_HINT_RE.search(label)):
                continue

            city = self._normalize_safe_city(label)
            if not city:
                continue

            normalized_city = normalize_entity_text(city)
            if normalized_city in seen:
                continue

            seen.add(normalized_city)
            result.append(
                PosterOccurrenceDraft(
                    city_name=city,
                    raw_line=label,
                )
            )

        return result

    def _extract_city_link_candidate(self, line: str) -> tuple[str | None, str | None]:
        urls = extract_urls(line)
        if not urls:
            return None, None

        for separator in CITY_LINK_SEPARATORS:
            if separator not in line:
                continue

            left, right = line.split(separator, 1)
            city_candidate = clean_line(left)
            rest = clean_line(right)

            if not city_candidate or not rest:
                continue

            if not extract_urls(rest):
                continue

            if self._is_url_like_value(city_candidate):
                continue

            if self._looks_like_semantic_field_label(city_candidate):
                continue

            if NON_CITY_VALUE_RE.search(city_candidate):
                continue

            if is_metadata_line(city_candidate):
                continue

            city = self._normalize_safe_city(city_candidate)
            if not city:
                continue

            return city, rest

        return None, None

    def _extract_single_occurrence(
        self,
        lines: list[str],
        title: str | None,
        artist_names: list[str],
        published_at: datetime | None,
    ) -> PosterOccurrenceDraft | None:
        event_date, raw_date_text, date_line = self._extract_event_date(
            lines=lines,
            published_at=published_at,
        )

        timings = self._extract_timings(lines)
        city_name = self._extract_city_name(lines, artist_names)
        venue_name = self._extract_venue_name(lines, title, artist_names, city_name)
        address = self._extract_address(lines)

        if not city_name:
            city_name = self._extract_city_from_inline_date_city_line(lines)

        if not city_name:
            city_name = self._extract_city_from_sentences(lines)

        if date_line and not city_name and not venue_name:
            inferred_city, inferred_venue = self._extract_city_and_venue_from_sentence(date_line)
            city_name = city_name or inferred_city
            venue_name = venue_name or inferred_venue

        if city_name:
            city_name = self._normalize_safe_city(city_name)

        occurrence = PosterOccurrenceDraft(
            city_name=city_name,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            timings=timings,
            raw_date_text=raw_date_text,
            raw_line=date_line or self._find_main_info_line(lines),
        )

        if (
            occurrence.city_name is None
            and occurrence.venue_name is None
            and occurrence.address is None
            and occurrence.event_date is None
            and not occurrence.timings
        ):
            return None

        return occurrence

    def _extract_event_date(
        self,
        lines: list[str],
        published_at: datetime | None,
    ) -> tuple[date | None, str | None, str | None]:
        for line in lines:
            raw_line = clean_line(line)
            parsed_line = self._prepare_line_for_parsing(line)

            if not raw_line or not parsed_line:
                continue

            labeled_date = extract_labeled_value(parsed_line, LABELED_DATE_REGEX)
            if labeled_date:
                date_result = self._parse_date_result(
                    text=labeled_date,
                    published_at=published_at,
                )
                if date_result is not None:
                    return date_result.start_date, date_result.raw_text, raw_line

            date_result = self._parse_date_result(
                text=parsed_line,
                published_at=published_at,
            )
            if date_result is not None:
                return date_result.start_date, date_result.raw_text, raw_line

        return None, None, None

    def _parse_date_result(
        self,
        text: str | None,
        published_at: datetime | None,
    ) -> DateResult | None:
        if not text:
            return None

        reference_date = published_at.date() if published_at else None
        default_year = published_at.year if published_at else None

        date_result = extract_date_range(
            text=text,
            default_year=default_year,
            reference_date=reference_date,
        )
        if date_result is not None:
            return date_result

        english_match = ENGLISH_DATE_RE.search(text)
        if english_match:
            day = int(english_match.group("day"))
            month = ENGLISH_MONTHS.get(english_match.group("month").lower())
            year_str = english_match.group("year")
            year = int(year_str) if year_str else (default_year or datetime.now().year)

            if month is not None:
                try:
                    parsed_date = date(year, month, day)
                except ValueError:
                    return None

                return DateResult(
                    start_date=parsed_date,
                    end_date=parsed_date,
                    raw_text=english_match.group(0),
                    source=DateSource.EXPLICIT,
                )

        dotted_match = DOTTED_DATE_ANY_RE.search(text)
        if dotted_match:
            day = int(dotted_match.group("day"))
            month = int(dotted_match.group("month"))
            year = default_year or datetime.now().year

            if dotted_match.group("year"):
                year = int(dotted_match.group("year"))
                if year < 100:
                    year += 2000

            try:
                parsed_date = date(year, month, day)
            except ValueError:
                return None

            return DateResult(
                start_date=parsed_date,
                end_date=parsed_date,
                raw_text=dotted_match.group(0),
                source=DateSource.EXPLICIT,
            )

        return None

    def _extract_timings(self, lines: list[str]) -> list:
        result: list = []

        for line in lines:
            raw_line = clean_line(line)
            parsed_line = self._prepare_line_for_parsing(line)

            if not raw_line or not parsed_line:
                continue

            if DOTTED_DATE_LINE_RE.match(parsed_line) and ":" not in parsed_line:
                continue

            if extract_labeled_value(parsed_line, LABELED_DATE_REGEX):
                continue

            if is_ticket_like_line(parsed_line):
                continue

            result.extend(extract_timings(parsed_line))

        return self._deduplicate_timings(result)

    def _deduplicate_timings(self, timings: list) -> list:
        seen: set[tuple[str | None, object, str | None]] = set()
        result: list = []

        for timing in timings:
            key = (timing.label, timing.time, timing.raw_time_text)
            if key in seen:
                continue

            seen.add(key)
            result.append(timing)

        return result

    def _extract_city_name(self, lines: list[str], artist_names: list[str]) -> str | None:
        artist_set = {
            normalize_entity_text(name)
            for name in artist_names
            if name.strip()
        }

        for index, line in enumerate(lines):
            raw_line = clean_line(line)
            parsed_line = self._prepare_line_for_parsing(line)

            if not raw_line or not parsed_line:
                continue

            normalized = normalize_entity_text(parsed_line)

            if index == 0:
                continue

            if normalized in artist_set:
                continue

            if normalized in NON_CITY_EXACT_VALUES:
                continue

            if self._looks_like_semantic_field_label(parsed_line):
                continue

            if NON_CITY_VALUE_RE.search(parsed_line):
                continue

            if is_metadata_line(parsed_line):
                continue

            if is_service_line(parsed_line):
                continue

            if is_price_line(parsed_line):
                continue

            if "|" in parsed_line or "/" in parsed_line or "," in parsed_line:
                continue

            if len(parsed_line) > MAX_CITY_LINE_LENGTH:
                continue

            words_count = len(parsed_line.split())
            if 1 <= words_count <= CITY_LABEL_MAX_WORDS and (
                parsed_line[:1].isupper() or CITY_HINT_RE.search(parsed_line)
            ):
                city = self._normalize_safe_city(parsed_line)
                if city:
                    return city

        return None

    def _extract_city_from_inline_date_city_line(self, lines: list[str]) -> str | None:
        for line in lines:
            parsed_line = self._prepare_line_for_parsing(line)
            if not parsed_line:
                continue

            match = INLINE_DATE_CITY_RE.match(parsed_line)
            if not match:
                continue

            city = self._normalize_safe_city(match.group("city"))
            if city:
                return city

        return None

    def _extract_city_from_sentences(self, lines: list[str]) -> str | None:
        for line in lines:
            parsed_line = self._prepare_line_for_parsing(line)
            if not parsed_line:
                continue

            match = CITY_IN_SENTENCE_RE.search(parsed_line)
            if not match:
                continue

            city = self._normalize_safe_city(match.group("city"))
            if city:
                return city

        return None

    def _extract_venue_name(
        self,
        lines: list[str],
        title: str | None,
        artist_names: list[str],
        city_name: str | None,
    ) -> str | None:
        artist_set = {
            normalize_entity_text(name)
            for name in artist_names
            if name.strip()
        }
        city_normalized = normalize_entity_text(city_name)
        title_normalized = normalize_entity_text(title)

        for line in lines:
            raw_line = clean_line(line)
            parsed_line = self._prepare_line_for_parsing(line)

            if not raw_line or not parsed_line:
                continue

            normalized = normalize_entity_text(parsed_line)

            if normalized == title_normalized:
                continue

            if normalized in artist_set:
                continue

            if normalized == city_normalized:
                continue

            labeled_venue = extract_labeled_value(parsed_line, LABELED_VENUE_REGEX)
            if labeled_venue:
                return clean_line(labeled_venue)

            pipe_venue = self._extract_venue_from_pipe_time_line(parsed_line)
            if pipe_venue:
                return pipe_venue

            if self._looks_like_venue_hint_line(parsed_line):
                return parsed_line

            if is_non_venue_metadata_line(parsed_line):
                continue

            if NON_VENUE_VALUE_RE.search(parsed_line):
                continue

            if is_service_line(parsed_line):
                continue

            if is_price_line(parsed_line):
                continue

            inline_venue = self._extract_inline_venue_from_line(parsed_line)
            if inline_venue:
                return inline_venue

            for part in self._extract_pipe_parts(parsed_line):
                part_normalized = normalize_entity_text(part)

                if part_normalized in {title_normalized, city_normalized}:
                    continue

                if part_normalized in artist_set:
                    continue

                if is_metadata_line(part):
                    continue

                if NON_VENUE_VALUE_RE.search(part):
                    continue

                if is_service_line(part):
                    continue

                if is_price_line(part):
                    continue

                if len(part) < 2:
                    continue

                if self._looks_like_venue_hint_line(part):
                    return part

                return part

            if self._looks_like_standalone_venue_line(parsed_line):
                return parsed_line

        return None

    def _extract_venue_from_pipe_time_line(self, line: str) -> str | None:
        parts = self._extract_pipe_parts(line)
        if len(parts) != 2:
            return None

        if not extract_timings(parts[1]):
            return None

        if is_metadata_line(parts[0]) or is_price_line(parts[0]):
            return None

        return parts[0]

    def _extract_inline_venue_from_line(self, line: str) -> str | None:
        if is_price_line(line):
            return None

        if is_ticket_like_line(line):
            return None

        match = INLINE_VENUE_RE.search(line)
        if not match:
            return None

        venue = clean_line(match.group("venue"))
        if not venue:
            return None

        if is_price_line(venue):
            return None

        return venue

    def _extract_city_and_venue_from_sentence(self, line: str) -> tuple[str | None, str | None]:
        parsed_line = self._prepare_line_for_parsing(line)
        if not parsed_line:
            return None, None

        match = INLINE_CITY_DATE_RE.match(parsed_line)
        if match:
            city = self._normalize_safe_city(match.group("city"))
            venue = self._extract_inline_venue_from_line(match.group("rest"))
            return city, venue

        sentence_city = None
        sentence_city_match = CITY_IN_SENTENCE_RE.search(parsed_line)
        if sentence_city_match:
            sentence_city = self._normalize_safe_city(sentence_city_match.group("city"))

        venue = self._extract_inline_venue_from_line(parsed_line)
        return sentence_city, venue

    def _looks_like_venue_hint_line(self, line: str) -> bool:
        lowered = normalize_entity_text(line)
        if not lowered:
            return False

        if is_metadata_line(line):
            return False

        if is_service_line(line):
            return False

        if is_price_line(line):
            return False

        return any(word in lowered for word in VENUE_HINT_WORDS)

    def _looks_like_standalone_venue_line(self, line: str) -> bool:
        if is_metadata_line(line):
            return False

        if is_service_line(line):
            return False

        if is_price_line(line):
            return False

        if len(line) > MAX_VENUE_LINE_LENGTH:
            return False

        if "," in line:
            return False

        if len(line.split()) > 5:
            return False

        return bool(re.search(r"[A-Za-zА-Яа-яЁё]", line))

    def _looks_like_semantic_field_label(self, value: str) -> bool:
        cleaned = clean_line(value)
        if not cleaned:
            return False

        normalized = normalize_entity_text(cleaned)
        if not normalized:
            return False

        return bool(SEMANTIC_FIELD_LABEL_RE.match(normalized))

    def _extract_pipe_parts(self, line: str) -> list[str]:
        if "|" not in line:
            return []

        return [
            clean_line(part)
            for part in line.split("|")
            if clean_line(part)
        ]

    def _split_venue_and_city(self, value: str) -> tuple[str | None, str | None]:
        cleaned = clean_line(value)

        tokens = cleaned.split()
        if len(tokens) >= 2 and tokens[-1].isupper():
            city = self._normalize_safe_city(tokens[-1])
            venue = clean_line(" ".join(tokens[:-1]))
            return venue or None, city or None

        match = CITY_ALIAS_RE.search(cleaned)
        if match:
            city = self._normalize_safe_city(match.group(0))
            venue = clean_line(cleaned[:match.start()] + cleaned[match.end():])
            return venue or None, city

        return cleaned or None, None

    def _extract_address(self, lines: list[str]) -> str | None:
        for line in lines:
            parsed_line = self._prepare_line_for_parsing(line)
            if not parsed_line:
                continue

            if is_metadata_line(parsed_line):
                continue

            if is_service_line(parsed_line):
                continue

            if is_price_line(parsed_line):
                continue

            if "," not in parsed_line or len(parsed_line) < 10:
                continue

            return parsed_line

        return None

    def _find_main_info_line(self, lines: list[str]) -> str | None:
        for line in lines:
            raw_line = clean_line(line)
            parsed_line = self._prepare_line_for_parsing(line)

            if not raw_line or not parsed_line:
                continue

            if extract_labeled_value(parsed_line, LABELED_DATE_REGEX):
                return raw_line

            if is_date_like_line(parsed_line):
                return raw_line

            if DOTTED_DATE_LINE_RE.match(parsed_line):
                return raw_line

        return clean_line(lines[1]) if len(lines) > 1 else None

    def _normalize_safe_city(self, value: str | None) -> str | None:
        if not value:
            return None

        if not self._is_safe_city_candidate(value):
            return None

        city = normalize_city_name(value)
        if not city:
            return None

        if not self._is_safe_city_candidate(city):
            return None

        return city

    def _is_safe_city_candidate(self, value: str | None) -> bool:
        if not value:
            return False

        cleaned = clean_line(value)
        if not cleaned:
            return False

        normalized = normalize_entity_text(cleaned)
        if not normalized:
            return False

        if normalized in NON_CITY_EXACT_VALUES:
            return False

        if normalized in BAD_CITY_VALUES:
            return False

        if self._is_url_like_value(cleaned):
            return False

        if cleaned.startswith("@"):
            return False

        if "." in cleaned or "/" in cleaned or "\\" in cleaned:
            return False

        if len(cleaned.split()) > CITY_LABEL_MAX_WORDS:
            return False

        if len(cleaned) > MAX_CITY_LINE_LENGTH:
            return False

        if re.search(r"\d", cleaned):
            return False

        if self._looks_like_semantic_field_label(cleaned):
            return False

        return True

    def _is_url_like_value(self, value: str | None) -> bool:
        if not value:
            return False

        lowered = value.strip().casefold()
        if not lowered:
            return False

        if lowered.startswith(("http://", "https://", "www.", "t.me/", "vk.com/")):
            return True

        if "://" in lowered:
            return True

        return bool(extract_urls(value))

    def _is_url_only_line(self, value: str | None) -> bool:
        if not value:
            return False

        cleaned = clean_line(value)
        if not cleaned:
            return False

        urls = extract_urls(cleaned)
        if not urls:
            return False

        without_urls = cleaned
        for url in urls:
            without_urls = without_urls.replace(url, " ")

        without_urls = clean_line(without_urls)
        return not without_urls

    def _prepare_line_for_parsing(self, value: str | None) -> str:
        if not value:
            return ''
        
        cleaned = clean_line(value)
        if not cleaned:
            return ''

        urls = extract_urls(cleaned)
        if not urls:
            return cleaned

        parsed = cleaned
        for url in urls:
            parsed = parsed.replace(url, " ")

        parsed = re.sub(r"\s+", " ", parsed).strip(" ,;:()[]{}|-–—")
        return clean_line(parsed)
    
