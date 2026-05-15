from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.application.poster_agent.verification_enums import (
    PosterAgentFactStatus,
    PosterAgentSourceType,
)
from app.application.poster_agent.verification_models import (
    PosterAgentVerificationFact,
    PosterAgentVerificationLink,
    PosterAgentVerificationOccurrence,
    PosterAgentVerificationResult,
)


@dataclass(slots=True)
class UrlEvidencePage:
    url: str
    final_url: str | None
    title: str | None
    description: str | None
    text_preview: str
    ok: bool
    blocked_by_antibot: bool
    status_code: int | None

    @property
    def source_url(self) -> str:
        return self.final_url or self.url

    @property
    def searchable_text(self) -> str:
        return "\n".join(
            part
            for part in [
                self.url,
                self.final_url,
                self.title,
                self.description,
                self.text_preview,
            ]
            if part
        )


@dataclass(slots=True)
class UrlEvidenceMatch:
    page: UrlEvidencePage
    matched_fields: set[str]
    confidence: float


class PosterUrlEvidenceVerifier:
    def apply(
        self,
        verification_result: PosterAgentVerificationResult,
        tool_outputs: list[Any],
    ) -> bool:
        pages = self._read_pages(tool_outputs)

        if not pages:
            return False

        changed = False

        for occurrence in verification_result.occurrences:
            match = self._find_occurrence_match(
                verification_result=verification_result,
                occurrence=occurrence,
                pages=pages,
            )

            if match is None:
                continue

            changed = self._verify_occurrence(occurrence, match) or changed
            changed = self._verify_related_facts(
                verification_result=verification_result,
                match=match,
            ) or changed

        for link in verification_result.links:
            match = self._find_link_match(link, pages)

            if match is None:
                continue

            changed = self._verify_link(link, match) or changed

        if changed:
            self._raise_overall_confidence(verification_result)

        return changed

    def _read_pages(
        self,
        tool_outputs: list[Any],
    ) -> list[UrlEvidencePage]:
        result: list[UrlEvidencePage] = []

        for tool_output in tool_outputs:
            tool_name = self._read_tool_output_name(tool_output)

            if tool_name != "url_read":
                continue

            data = self._read_tool_output_data(tool_output)

            if not isinstance(data, dict):
                continue

            raw_pages = data.get("pages")

            if not isinstance(raw_pages, list):
                continue

            for item in raw_pages:
                page = self._read_page(item)

                if page is None:
                    continue

                if not self._page_is_usable(page):
                    continue

                result.append(page)

        return result

    def _read_tool_output_name(
        self,
        tool_output: Any,
    ) -> str | None:
        if isinstance(tool_output, dict):
            value = tool_output.get("tool_name")
        else:
            value = getattr(tool_output, "tool_name", None)

        if isinstance(value, str) and value.strip():
            return value.strip()

        return None


    def _read_tool_output_data(
        self,
        tool_output: Any,
    ) -> Any:
        if isinstance(tool_output, dict):
            return tool_output.get("data")

        return getattr(tool_output, "data", None)

    def _read_page(
        self,
        value: Any,
    ) -> UrlEvidencePage | None:
        if not isinstance(value, dict):
            return None

        url = self._read_string(value.get("url"))

        if url is None:
            return None

        return UrlEvidencePage(
            url=url,
            final_url=self._read_string(value.get("final_url")),
            title=self._read_string(value.get("title")),
            description=self._read_string(value.get("description")),
            text_preview=self._read_string(value.get("text_preview")) or "",
            ok=self._read_bool(value.get("ok")),
            blocked_by_antibot=self._read_bool(value.get("blocked_by_antibot")),
            status_code=self._read_int(value.get("status_code")),
        )

    def _page_is_usable(
        self,
        page: UrlEvidencePage,
    ) -> bool:
        if not page.ok:
            return False

        if page.blocked_by_antibot:
            return False

        if page.status_code is None:
            return True

        return 200 <= page.status_code < 400

    def _find_occurrence_match(
        self,
        verification_result: PosterAgentVerificationResult,
        occurrence: PosterAgentVerificationOccurrence,
        pages: list[UrlEvidencePage],
    ) -> UrlEvidenceMatch | None:
        best_match: UrlEvidenceMatch | None = None

        for page in pages:
            matched_fields = self._match_occurrence_fields(
                verification_result=verification_result,
                occurrence=occurrence,
                page=page,
            )

            if not self._is_strong_occurrence_match(
                verification_result=verification_result,
                occurrence=occurrence,
                matched_fields=matched_fields,
            ):
                continue

            confidence = self._score_occurrence_match(matched_fields)

            match = UrlEvidenceMatch(
                page=page,
                matched_fields=matched_fields,
                confidence=confidence,
            )

            if best_match is None or match.confidence > best_match.confidence:
                best_match = match

        return best_match

    def _match_occurrence_fields(
        self,
        verification_result: PosterAgentVerificationResult,
        occurrence: PosterAgentVerificationOccurrence,
        page: UrlEvidencePage,
    ) -> set[str]:
        matched_fields: set[str] = set()

        if self._matches_any_artist(verification_result.artists, page):
            matched_fields.add("artist")

        if occurrence.event_date and self._contains_value(
            page.searchable_text,
            occurrence.event_date,
            field="date",
        ):
            matched_fields.add("date")

        if occurrence.city_name and self._contains_value(
            page.searchable_text,
            occurrence.city_name,
            field="city",
        ):
            matched_fields.add("city")

        if occurrence.venue_name and self._contains_value(
            page.searchable_text,
            occurrence.venue_name,
            field="venue",
        ):
            matched_fields.add("venue")

        if occurrence.address and self._contains_value(
            page.searchable_text,
            occurrence.address,
            field="address",
        ):
            matched_fields.add("address")

        return matched_fields

    def _is_strong_occurrence_match(
        self,
        verification_result: PosterAgentVerificationResult,
        occurrence: PosterAgentVerificationOccurrence,
        matched_fields: set[str],
    ) -> bool:
        if verification_result.artists and "artist" not in matched_fields:
            return False

        if occurrence.event_date and "date" not in matched_fields:
            return False

        has_place_in_occurrence = bool(occurrence.city_name or occurrence.venue_name)
        has_place_match = bool({"city", "venue", "address"} & matched_fields)

        if has_place_in_occurrence and not has_place_match:
            return False

        return bool(matched_fields)

    def _score_occurrence_match(
        self,
        matched_fields: set[str],
    ) -> float:
        score = 0.7

        if "artist" in matched_fields:
            score += 0.08

        if "date" in matched_fields:
            score += 0.08

        if "city" in matched_fields:
            score += 0.05

        if "venue" in matched_fields:
            score += 0.07

        if "address" in matched_fields:
            score += 0.05

        return min(score, 0.98)

    def _verify_occurrence(
        self,
        occurrence: PosterAgentVerificationOccurrence,
        match: UrlEvidenceMatch,
    ) -> bool:
        changed = False

        if not occurrence.verified:
            occurrence.verified = True
            changed = True

        if occurrence.confidence < match.confidence:
            occurrence.confidence = match.confidence
            changed = True

        if occurrence.source_url != match.page.source_url:
            occurrence.source_url = match.page.source_url
            changed = True

        explanation = self._build_occurrence_explanation(match)

        if explanation not in (occurrence.explanation or ""):
            occurrence.explanation = self._append_explanation(
                occurrence.explanation,
                explanation,
            )
            changed = True

        return changed

    def _verify_related_facts(
        self,
        verification_result: PosterAgentVerificationResult,
        match: UrlEvidenceMatch,
    ) -> bool:
        changed = False

        for fact in verification_result.facts:
            normalized_field = self._normalize_fact_field(fact.field)

            if normalized_field not in match.matched_fields:
                continue

            if self._verify_fact(fact, match):
                changed = True

        return changed

    def _verify_fact(
        self,
        fact: PosterAgentVerificationFact,
        match: UrlEvidenceMatch,
    ) -> bool:
        changed = False

        if fact.status != PosterAgentFactStatus.VERIFIED:
            fact.status = PosterAgentFactStatus.VERIFIED
            changed = True

        if fact.source_type != PosterAgentSourceType.URL:
            fact.source_type = PosterAgentSourceType.URL
            changed = True

        if fact.confidence < match.confidence:
            fact.confidence = match.confidence
            changed = True

        if fact.source_url != match.page.source_url:
            fact.source_url = match.page.source_url
            changed = True

        if fact.source_title != match.page.title:
            fact.source_title = match.page.title
            changed = True

        explanation = "Факт найден на успешно прочитанной URL-странице."

        if explanation not in (fact.explanation or ""):
            fact.explanation = self._append_explanation(
                fact.explanation,
                explanation,
            )
            changed = True

        return changed

    def _find_link_match(
        self,
        link: PosterAgentVerificationLink,
        pages: list[UrlEvidencePage],
    ) -> UrlEvidenceMatch | None:
        for page in pages:
            if self._same_url(link.url, page.url) or self._same_url(
                link.url,
                page.final_url,
            ):
                return UrlEvidenceMatch(
                    page=page,
                    matched_fields={"link"},
                    confidence=self._score_link_match(link, page),
                )

        return None

    def _verify_link(
        self,
        link: PosterAgentVerificationLink,
        match: UrlEvidenceMatch,
    ) -> bool:
        if link.kind not in {"ticket", "official", "source"}:
            return False

        changed = False

        if not link.verified:
            link.verified = True
            changed = True

        if link.source_type != PosterAgentSourceType.URL:
            link.source_type = PosterAgentSourceType.URL
            changed = True

        if link.confidence < match.confidence:
            link.confidence = match.confidence
            changed = True

        if not link.title and match.page.title:
            link.title = match.page.title
            changed = True

        explanation = self._build_link_explanation(link, match.page)

        if explanation not in (link.explanation or ""):
            link.explanation = self._append_explanation(
                link.explanation,
                explanation,
            )
            changed = True

        return changed

    def _score_link_match(
        self,
        link: PosterAgentVerificationLink,
        page: UrlEvidencePage,
    ) -> float:
        if link.kind == "official":
            return 1.0

        if link.kind == "ticket":
            if self._looks_like_ticket_page(page):
                return 0.88

            return 0.8

        return 0.75

    def _looks_like_ticket_page(
        self,
        page: UrlEvidencePage,
    ) -> bool:
        text = self._normalize_text(page.searchable_text)

        markers = [
            "ticketscloud",
            "ticket",
            "билет",
            "билеты",
            "widget",
        ]

        return any(marker in text for marker in markers)

    def _raise_overall_confidence(
        self,
        verification_result: PosterAgentVerificationResult,
    ) -> None:
        has_verified_occurrence = any(
            occurrence.verified
            for occurrence in verification_result.occurrences
        )
        has_verified_link = any(
            link.verified and link.kind in {"ticket", "official", "source"}
            for link in verification_result.links
        )

        if has_verified_occurrence and has_verified_link:
            verification_result.overall_confidence = max(
                verification_result.overall_confidence,
                0.85,
            )
            return

        if has_verified_occurrence or has_verified_link:
            verification_result.overall_confidence = max(
                verification_result.overall_confidence,
                0.7,
            )

    def _matches_any_artist(
        self,
        artists: list[str],
        page: UrlEvidencePage,
    ) -> bool:
        for artist in artists:
            if self._contains_value(page.searchable_text, artist, field="artist"):
                return True

        return False

    def _contains_value(
        self,
        text: str,
        value: Any,
        field: str,
    ) -> bool:
        if value is None:
            return False

        raw_value = str(value).strip()

        if not raw_value:
            return False

        normalized_text = self._normalize_text(text)

        for candidate in self._build_value_candidates(raw_value, field):
            normalized_candidate = self._normalize_text(candidate)

            if not normalized_candidate:
                continue

            if normalized_candidate in normalized_text:
                return True

        return False

    def _build_value_candidates(
        self,
        value: str,
        field: str,
    ) -> list[str]:
        result = [value]

        normalized_value = self._normalize_text(value)

        if field == "city":
            if normalized_value in {"санкт петербург", "с петербург"}:
                result.extend(
                    [
                        "Санкт-Петербург",
                        "С-Петербург",
                        "СПб",
                        "Питер",
                        "Санкт Петербург",
                    ]
                )

        if field == "date":
            dotted_match = re.fullmatch(
                r"0?([1-9]|[12]\d|3[01])\.0?([1-9]|1[0-2])(?:\.\d{4})?",
                value.strip(),
            )

            if dotted_match:
                day = int(dotted_match.group(1))
                month = int(dotted_match.group(2))
                month_name = self._month_name(month)

                if month_name:
                    result.append(f"{day} {month_name}")

        return self._deduplicate_strings(result)

    def _normalize_fact_field(
        self,
        field: str,
    ) -> str:
        value = field.strip().lower()

        aliases = {
            "artist": "artist",
            "artists": "artist",
            "артист": "artist",
            "артисты": "artist",
            "date": "date",
            "event_date": "date",
            "дата": "date",
            "city": "city",
            "город": "city",
            "venue": "venue",
            "place": "venue",
            "площадка": "venue",
            "место": "venue",
            "address": "address",
            "адрес": "address",
        }

        return aliases.get(value, value)

    def _build_occurrence_explanation(
        self,
        match: UrlEvidenceMatch,
    ) -> str:
        fields = ", ".join(sorted(match.matched_fields))

        if match.page.title:
            return (
                f"Дата/город/площадка подтверждены URL-страницей "
                f"«{match.page.title}»: {fields}."
            )

        return f"Дата/город/площадка подтверждены URL-страницей: {fields}."

    def _build_link_explanation(
        self,
        link: PosterAgentVerificationLink,
        page: UrlEvidencePage,
    ) -> str:
        if link.kind == "ticket" and self._looks_like_ticket_page(page):
            return "Ссылка успешно прочитана и ведёт на билетный сервис."

        if link.kind == "official":
            return "Официальная ссылка успешно прочитана."

        return "Ссылка успешно прочитана."

    def _same_url(
        self,
        left: str | None,
        right: str | None,
    ) -> bool:
        left_key = self._normalize_url(left)
        right_key = self._normalize_url(right)

        return bool(left_key and right_key and left_key == right_key)

    def _normalize_url(
        self,
        value: str | None,
    ) -> str:
        if not value:
            return ""

        stripped = value.strip().lower()

        while stripped.endswith("/"):
            stripped = stripped[:-1]

        return stripped

    def _normalize_text(
        self,
        value: str,
    ) -> str:
        text = value.lower().replace("ё", "е")
        text = re.sub(r"[^0-9a-zа-я]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _read_string(
        self,
        value: Any,
    ) -> str | None:
        if not isinstance(value, str):
            return None

        stripped = value.strip()

        if not stripped:
            return None

        return stripped

    def _read_bool(
        self,
        value: Any,
    ) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "да"}

        return False

    def _read_int(
        self,
        value: Any,
    ) -> int | None:
        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return None

        return None

    def _append_explanation(
        self,
        current: str | None,
        addition: str,
    ) -> str:
        if not current:
            return addition

        if addition in current:
            return current

        return f"{current.strip()} {addition}"

    def _deduplicate_strings(
        self,
        values: list[str],
    ) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            key = self._normalize_text(value)

            if not key or key in seen:
                continue

            seen.add(key)
            result.append(value)

        return result

    def _month_name(
        self,
        month: int,
    ) -> str | None:
        names = {
            1: "января",
            2: "февраля",
            3: "марта",
            4: "апреля",
            5: "мая",
            6: "июня",
            7: "июля",
            8: "августа",
            9: "сентября",
            10: "октября",
            11: "ноября",
            12: "декабря",
        }

        return names.get(month)
    