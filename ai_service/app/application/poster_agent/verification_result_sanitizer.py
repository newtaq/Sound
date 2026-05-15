import re
from typing import Any
from urllib.parse import urlparse

from app.application.agent_core import AgentRun
from app.application.poster_agent.pipeline_goal_builder import (
    PosterAgentPipelineGoalBuilder,
)
from app.application.poster_agent.pipeline_models import PosterAgentPipelineRequest
from app.application.poster_agent.verification_enums import (
    PosterAgentFactStatus,
    PosterAgentSourceType,
    PosterAgentVerificationRecommendation,
)
from app.application.poster_agent.verification_models import (
    PosterAgentVerificationResult,
)


class PosterAgentVerificationResultSanitizer:
    _INSUFFICIENT_VERIFICATION_WARNING = (
        "Verifier-agent вернул данные как verified без достаточной проверки."
    )

    def __init__(
        self,
        goal_builder: PosterAgentPipelineGoalBuilder | None = None,
    ) -> None:
        self._goal_builder = goal_builder or PosterAgentPipelineGoalBuilder()

    def sanitize(
        self,
        verification_result: PosterAgentVerificationResult,
        request: PosterAgentPipelineRequest,
        urls_for_verification: list[str],
    ) -> None:
        original_date = self._goal_builder.read_input_event_date(request)
        date_has_year = self._goal_builder.request_date_has_year(request)
        manual_enabled = self._goal_builder.manual_confirmation_enabled(request)
        url_verification_enabled = request.use_url_read and bool(urls_for_verification)
        changed_critical_fact = False

        verification_result.warnings = [
            warning
            for warning in verification_result.warnings
            if warning != self._INSUFFICIENT_VERIFICATION_WARNING
        ]

        trusted_sources = {
            PosterAgentSourceType.URL,
            PosterAgentSourceType.DATABASE,
        }

        if manual_enabled:
            trusted_sources.add(PosterAgentSourceType.MANUAL)

        for occurrence in verification_result.occurrences:
            if occurrence.event_date:
                sanitized_date = self._sanitize_event_date(
                    value=occurrence.event_date,
                    original_date=original_date,
                    date_has_year=date_has_year,
                )

                if sanitized_date != occurrence.event_date:
                    occurrence.event_date = sanitized_date
                    occurrence.verified = False
                    occurrence.confidence = min(
                        self._read_confidence(occurrence.confidence),
                        0.5,
                    )
                    occurrence.explanation = self._append_explanation(
                        occurrence.explanation,
                        "Год был удалён, потому что он не подтверждён входными данными.",
                    )
                    changed_critical_fact = True

            if occurrence.verified and not url_verification_enabled and not manual_enabled:
                occurrence.verified = False
                occurrence.confidence = min(
                    self._read_confidence(occurrence.confidence),
                    0.5,
                )
                occurrence.explanation = self._append_explanation(
                    occurrence.explanation,
                    "Дата/город не могут быть verified без внешней проверки или manual.",
                )
                changed_critical_fact = True

            if occurrence.verified and not occurrence.source_url and not manual_enabled:
                occurrence.verified = False
                occurrence.confidence = min(
                    self._read_confidence(occurrence.confidence),
                    0.5,
                )
                occurrence.explanation = self._append_explanation(
                    occurrence.explanation,
                    "Дата/город не могут быть verified без проверяемого source_url.",
                )
                changed_critical_fact = True

        for link in verification_result.links:
            if self._is_telegram_url(link.url) and link.kind == "official":
                link.kind = "social"

            if link.verified and not url_verification_enabled and not manual_enabled:
                link.verified = False
                link.confidence = min(
                    self._read_confidence(link.confidence),
                    0.5,
                )
                link.explanation = self._append_explanation(
                    link.explanation,
                    "Ссылка не может быть verified без внешней проверки или manual.",
                )
                changed_critical_fact = True

            if link.verified and link.source_type not in trusted_sources:
                link.verified = False
                link.confidence = min(
                    self._read_confidence(link.confidence),
                    0.5,
                )
                link.explanation = self._append_explanation(
                    link.explanation,
                    "Ссылка не может быть verified только из input/ocr/qr/search.",
                )
                changed_critical_fact = True

        for fact in verification_result.facts:
            field_name = fact.field.strip().lower()

            if isinstance(fact.value, str) and field_name in {
                "date",
                "event_date",
                "дата",
            }:
                sanitized_date = self._sanitize_event_date(
                    value=fact.value,
                    original_date=original_date,
                    date_has_year=date_has_year,
                )

                if sanitized_date != fact.value:
                    fact.value = sanitized_date
                    fact.status = PosterAgentFactStatus.UNVERIFIED
                    fact.confidence = min(
                        self._read_confidence(fact.confidence),
                        0.5,
                    )
                    fact.explanation = self._append_explanation(
                        fact.explanation,
                        "Год был удалён, потому что он не подтверждён входными данными.",
                    )
                    changed_critical_fact = True

            if fact.status == PosterAgentFactStatus.VERIFIED:
                if not url_verification_enabled and not manual_enabled:
                    fact.status = PosterAgentFactStatus.UNVERIFIED
                    fact.confidence = min(
                        self._read_confidence(fact.confidence),
                        0.5,
                    )
                    fact.explanation = self._append_explanation(
                        fact.explanation,
                        "Факт не может быть verified без внешней проверки или manual.",
                    )
                    changed_critical_fact = True
                    continue

                if fact.source_type not in trusted_sources:
                    fact.status = PosterAgentFactStatus.UNVERIFIED
                    fact.confidence = min(
                        self._read_confidence(fact.confidence),
                        0.5,
                    )
                    fact.explanation = self._append_explanation(
                        fact.explanation,
                        "Факт не может быть verified только из input/ocr/qr/search.",
                    )
                    changed_critical_fact = True

        if changed_critical_fact:
            verification_result.recommendation = (
                PosterAgentVerificationRecommendation.NEEDS_REVIEW
            )
            verification_result.overall_confidence = min(
                self._read_confidence(verification_result.overall_confidence),
                0.5,
            )

            if self._INSUFFICIENT_VERIFICATION_WARNING not in verification_result.warnings:
                verification_result.warnings.append(
                    self._INSUFFICIENT_VERIFICATION_WARNING
                )

        self.normalize_recommendation(verification_result)

    def apply_url_read_confirmation(
        self,
        agent_run: AgentRun,
        verification_result: PosterAgentVerificationResult,
        request: PosterAgentPipelineRequest,
    ) -> None:
        if not request.use_url_read:
            return

        pages = self.read_url_read_pages(agent_run)

        if not pages:
            return

        changed = False

        for occurrence in verification_result.occurrences:
            page = self._find_page_for_occurrence(
                pages=pages,
                occurrence=occurrence,
                verification_result=verification_result,
            )

            if page is None:
                continue

            occurrence.verified = True
            occurrence.confidence = max(
                self._read_confidence(occurrence.confidence),
                0.9,
            )
            occurrence.source_url = self._read_page_source_url(page)
            occurrence.explanation = self._append_explanation(
                occurrence.explanation,
                "Дата, город и площадка подтверждены прямым чтением URL.",
            )

            if not occurrence.address:
                address = self._extract_address_from_page(page)

                if address:
                    occurrence.address = address

            changed = True

        for link in verification_result.links:
            page = self._find_page_for_link(
                pages=pages,
                link_url=link.url,
            )

            if page is None:
                continue

            link.source_type = PosterAgentSourceType.URL
            link.confidence = max(
                self._read_confidence(link.confidence),
                0.5,
            )

            if not link.title:
                title = self._read_page_string(page, "title")

                if title:
                    link.title = title

            if self._link_is_confirmed_by_page(
                page=page,
                link_kind=link.kind,
                verification_result=verification_result,
            ):
                link.verified = True
                link.confidence = max(
                    self._read_confidence(link.confidence),
                    0.9,
                )
                link.explanation = self._append_explanation(
                    link.explanation,
                    "Ссылка подтверждена прямым чтением URL.",
                )
                changed = True
                continue

            if self._is_ticket_like_page(page):
                link.explanation = self._append_explanation(
                    link.explanation,
                    (
                        "Ссылка раскрылась до билетного сервиса, но страница "
                        "не содержит достаточно фактов события."
                    ),
                )
                changed = True

        for fact in verification_result.facts:
            if self._verify_fact_by_pages(
                pages=pages,
                fact=fact,
                verification_result=verification_result,
            ):
                changed = True

        if changed:
            self.normalize_recommendation(verification_result)

    def normalize_recommendation(
        self,
        verification_result: PosterAgentVerificationResult,
    ) -> None:
        has_verified_occurrence = any(
            occurrence.verified
            for occurrence in verification_result.occurrences
        )
        has_verified_publish_link = any(
            link.verified and link.kind in {"ticket", "official", "source"}
            for link in verification_result.links
        )
        has_unverified_ticket = any(
            link.kind == "ticket" and not link.verified
            for link in verification_result.links
        )

        if not has_verified_occurrence or not has_verified_publish_link:
            verification_result.recommendation = (
                PosterAgentVerificationRecommendation.NEEDS_REVIEW
            )
            verification_result.overall_confidence = min(
                self._read_confidence(verification_result.overall_confidence),
                0.8,
            )
            return

        if has_unverified_ticket:
            verification_result.recommendation = (
                PosterAgentVerificationRecommendation.NEEDS_REVIEW
            )
            verification_result.overall_confidence = min(
                max(self._read_confidence(verification_result.overall_confidence), 0.75),
                0.84,
            )
            return

        if not verification_result.conflicts and not verification_result.missing_fields:
            verification_result.overall_confidence = max(
                self._read_confidence(verification_result.overall_confidence),
                0.9,
            )

    def read_url_read_pages(
        self,
        agent_run: AgentRun,
    ) -> list[dict[str, Any]]:
        if agent_run.final_result is None:
            return []

        raw_tool_results = agent_run.final_result.structured_data.get("tool_results")

        if not isinstance(raw_tool_results, list):
            return []

        pages: list[dict[str, Any]] = []

        for raw_tool_result in raw_tool_results:
            if not isinstance(raw_tool_result, dict):
                continue

            if raw_tool_result.get("tool_name") != "url_read":
                continue

            data = raw_tool_result.get("data")

            if not isinstance(data, dict):
                continue

            raw_pages = data.get("pages")

            if not isinstance(raw_pages, list):
                continue

            for raw_page in raw_pages:
                if isinstance(raw_page, dict):
                    pages.append(raw_page)

        return pages

    def _find_page_for_occurrence(
        self,
        pages: list[dict[str, Any]],
        occurrence: Any,
        verification_result: PosterAgentVerificationResult,
    ) -> dict[str, Any] | None:
        candidates: list[tuple[int, dict[str, Any]]] = []

        for page in pages:
            if not self._page_is_readable(page):
                continue

            score = 0

            if occurrence.city_name and self._page_contains_city(
                page=page,
                city=occurrence.city_name,
            ):
                score += 1

            if occurrence.venue_name and self._page_contains(
                page=page,
                value=occurrence.venue_name,
            ):
                score += 1

            if occurrence.event_date and self._page_contains_date(
                page=page,
                date_value=occurrence.event_date,
            ):
                score += 1

            if verification_result.title and self._page_contains(
                page=page,
                value=verification_result.title,
            ):
                score += 1

            if verification_result.artists and any(
                self._page_contains(page=page, value=artist)
                for artist in verification_result.artists
            ):
                score += 1

            if score >= 3:
                candidates.append((score, page))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _find_page_for_link(
        self,
        pages: list[dict[str, Any]],
        link_url: str,
    ) -> dict[str, Any] | None:
        link_domain = self._extract_domain(link_url)

        if not link_domain:
            return None

        for page in pages:
            if not self._page_is_readable(page):
                continue

            for page_url in (
                self._read_page_string(page, "url"),
                self._read_page_string(page, "final_url"),
            ):
                if page_url and self._extract_domain(page_url) == link_domain:
                    return page

        for page in pages:
            if not self._page_is_readable(page):
                continue

            for page_url in (
                self._read_page_string(page, "url"),
                self._read_page_string(page, "final_url"),
            ):
                page_domain = self._extract_domain(page_url)

                if not page_domain:
                    continue

                if page_domain.endswith(link_domain) or link_domain.endswith(page_domain):
                    return page

        return None

    def _link_is_confirmed_by_page(
        self,
        page: dict[str, Any],
        link_kind: str,
        verification_result: PosterAgentVerificationResult,
    ) -> bool:
        if link_kind not in {"ticket", "official", "source"}:
            return False

        score = 0

        if verification_result.title and self._page_contains(
            page=page,
            value=verification_result.title,
        ):
            score += 1

        if verification_result.artists and any(
            self._page_contains(page=page, value=artist)
            for artist in verification_result.artists
        ):
            score += 1

        for occurrence in verification_result.occurrences:
            if occurrence.event_date and self._page_contains_date(
                page=page,
                date_value=occurrence.event_date,
            ):
                score += 1

            if occurrence.city_name and self._page_contains_city(
                page=page,
                city=occurrence.city_name,
            ):
                score += 1

            if occurrence.venue_name and self._page_contains(
                page=page,
                value=occurrence.venue_name,
            ):
                score += 1

        if score >= 3:
            return True

        if link_kind == "ticket" and self._is_ticket_like_page(page) and score >= 2:
            return True

        return False

    def _verify_fact_by_pages(
        self,
        pages: list[dict[str, Any]],
        fact: Any,
        verification_result: PosterAgentVerificationResult,
    ) -> bool:
        if not isinstance(fact.value, str) or not fact.value.strip():
            return False

        field_name = fact.field.strip().lower()

        for page in pages:
            if not self._page_is_readable(page):
                continue

            if not self._page_contains_fact(
                page=page,
                field_name=field_name,
                value=fact.value,
                verification_result=verification_result,
            ):
                continue

            fact.status = PosterAgentFactStatus.VERIFIED
            fact.source_type = PosterAgentSourceType.URL
            fact.confidence = max(
                self._read_confidence(fact.confidence),
                0.9,
            )
            fact.source_url = self._read_page_source_url(page)
            fact.source_title = self._read_page_string(page, "title")
            fact.explanation = self._append_explanation(
                fact.explanation,
                "Факт подтверждён прямым чтением URL.",
            )
            return True

        return False

    def _page_contains_fact(
        self,
        page: dict[str, Any],
        field_name: str,
        value: str,
        verification_result: PosterAgentVerificationResult,
    ) -> bool:
        if field_name in {"date", "event_date", "дата"}:
            return self._page_contains_date(page=page, date_value=value)

        if field_name in {"city", "город"}:
            return self._page_contains_city(page=page, city=value)

        if field_name in {"artist", "артист"}:
            return self._page_contains(page=page, value=value)

        if field_name in {"venue", "place", "площадка", "место"}:
            return self._page_contains(page=page, value=value)

        if field_name in {"address", "адрес"}:
            return self._page_contains(page=page, value=value)

        if field_name in {"ticket_link", "official_source", "source", "link"}:
            return self._page_contains_link_fact(
                page=page,
                value=value,
                verification_result=verification_result,
            )

        return False

    def _page_contains_link_fact(
        self,
        page: dict[str, Any],
        value: str,
        verification_result: PosterAgentVerificationResult,
    ) -> bool:
        domain = self._extract_domain(value)

        if domain:
            for page_url in (
                self._read_page_string(page, "url"),
                self._read_page_string(page, "final_url"),
            ):
                page_domain = self._extract_domain(page_url)

                if page_domain and (
                    page_domain == domain
                    or page_domain.endswith(domain)
                    or domain.endswith(page_domain)
                ):
                    return self._link_is_confirmed_by_page(
                        page=page,
                        link_kind="official",
                        verification_result=verification_result,
                    )

        return self._page_contains(page=page, value=value)

    def _page_is_readable(
        self,
        page: dict[str, Any],
    ) -> bool:
        if page.get("ok") is not True:
            return False

        if page.get("blocked_by_antibot") is True:
            return False

        return True

    def _is_ticket_like_page(
        self,
        page: dict[str, Any],
    ) -> bool:
        urls = [
            self._read_page_string(page, "url"),
            self._read_page_string(page, "final_url"),
        ]
        title = self._read_page_string(page, "title") or ""

        haystack = " ".join(
            value
            for value in [*urls, title]
            if value
        ).lower()

        return any(
            marker in haystack
            for marker in (
                "ticketscloud",
                "qtickets",
                "kassir",
                "radario",
                "ticketland",
                "tickets",
                "bilet",
                "билет",
            )
        )

    def _page_contains(
        self,
        page: dict[str, Any],
        value: str,
    ) -> bool:
        normalized_value = self._normalize_search_text(value)

        if not normalized_value:
            return False

        return normalized_value in self._read_normalized_page_text(page)

    def _page_contains_city(
        self,
        page: dict[str, Any],
        city: str,
    ) -> bool:
        for alias in self._city_aliases(city):
            if self._page_contains(page=page, value=alias):
                return True

        return False

    def _page_contains_date(
        self,
        page: dict[str, Any],
        date_value: str,
    ) -> bool:
        for alias in self._date_aliases(date_value):
            if self._page_contains(page=page, value=alias):
                return True

        return False

    def _date_aliases(
        self,
        value: str,
    ) -> list[str]:
        stripped = value.strip()

        if not stripped:
            return []

        result = [stripped]

        iso_match = re.search(
            r"\b(20\d{2})-(0?[1-9]|1[0-2])-([0-2]?\d|3[01])\b",
            stripped,
        )

        if iso_match:
            _year, month, day = iso_match.groups()
            result.append(f"{int(day)} {self._month_name(int(month))}")
            result.append(f"{int(day):02d}.{int(month):02d}")

        dotted_match = re.search(
            r"\b([0-2]?\d|3[01])[.\-/](0?[1-9]|1[0-2])(?:[.\-/](20\d{2}))?\b",
            stripped,
        )

        if dotted_match:
            day, month, _year = dotted_match.groups()
            result.append(f"{int(day)} {self._month_name(int(month))}")
            result.append(f"{int(day):02d}.{int(month):02d}")

        month_match = re.search(
            (
                r"(?i)\b([0-2]?\d|3[01])\s+"
                r"(января|февраля|марта|апреля|мая|июня|июля|"
                r"августа|сентября|октября|ноября|декабря)"
                r"(?:\s+(20\d{2}))?\b"
            ),
            stripped,
        )

        if month_match:
            day, month_name, _year = month_match.groups()
            result.append(f"{int(day)} {month_name.lower()}")

        return self._deduplicate_strings(result)

    def _month_name(
        self,
        month: int,
    ) -> str:
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

        return names.get(month, "")

    def _city_aliases(
        self,
        city: str,
    ) -> list[str]:
        normalized = self._normalize_search_text(city)
        aliases = [city]

        if normalized in {
            "санкт петербург",
            "санктпетербург",
            "спб",
            "с петербург",
            "питер",
        }:
            aliases.extend(
                [
                    "Санкт-Петербург",
                    "Санкт Петербург",
                    "С-Петербург",
                    "СПб",
                    "Питер",
                ]
            )

        return self._deduplicate_strings(aliases)

    def _read_normalized_page_text(
        self,
        page: dict[str, Any],
    ) -> str:
        parts = [
            self._read_page_string(page, "url"),
            self._read_page_string(page, "final_url"),
            self._read_page_string(page, "title"),
            self._read_page_string(page, "description"),
            self._read_page_string(page, "text_preview"),
        ]

        return self._normalize_search_text(
            " ".join(
                part
                for part in parts
                if part
            )
        )

    def _normalize_search_text(
        self,
        value: str,
    ) -> str:
        normalized = value.lower().replace("ё", "е")
        normalized = normalized.replace("–", "-").replace("—", "-")
        normalized = re.sub(r"[^\wа-яА-Я0-9]+", " ", normalized)
        return " ".join(normalized.split())

    def _read_page_source_url(
        self,
        page: dict[str, Any],
    ) -> str | None:
        return (
            self._read_page_string(page, "final_url")
            or self._read_page_string(page, "url")
        )

    def _read_page_string(
        self,
        page: dict[str, Any],
        key: str,
    ) -> str | None:
        value = page.get(key)

        if not isinstance(value, str):
            return None

        stripped = value.strip()

        if not stripped:
            return None

        return stripped

    def _extract_address_from_page(
        self,
        page: dict[str, Any],
    ) -> str | None:
        text = self._read_page_string(page, "text_preview")

        if not text:
            return None

        patterns = [
            (
                r"(?i)(?:санкт[-\s]?петербург|с[-\s]?петербург|спб)"
                r"\s*,\s*([^\.]+?\b\d+[а-яa-z]?)"
            ),
            r"(?i)(площадь\s+морской\s+славы\s*,?\s*1)",
            r"(?i)(ул\.?\s+[а-яёa-z0-9\s\-]+,\s*\d+[а-яa-z]?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)

            if match:
                return " ".join(match.group(1).split())

        return None

    def _extract_domain(
        self,
        url: str | None,
    ) -> str | None:
        if not url:
            return None

        prepared = url.strip()

        if not prepared:
            return None

        if "://" not in prepared:
            prepared = "https://" + prepared

        parsed = urlparse(prepared)
        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain or None

    def _sanitize_event_date(
        self,
        value: str,
        original_date: str | None,
        date_has_year: bool,
    ) -> str:
        stripped = value.strip()

        if date_has_year:
            return stripped

        if not original_date:
            return stripped

        if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", stripped):
            return original_date

        if re.search(r"\b\d{1,2}\.\d{1,2}\.20\d{2}\b", stripped):
            return original_date

        if re.search(
            (
                r"(?i)\b\d{1,2}\s+"
                r"(января|февраля|марта|апреля|мая|июня|июля|"
                r"августа|сентября|октября|ноября|декабря)"
                r"\s+20\d{2}\b"
            ),
            stripped,
        ):
            return original_date

        return stripped

    def _is_telegram_url(
        self,
        url: str,
    ) -> bool:
        return (
            "://t.me/" in url
            or "://telegram.me/" in url
            or url.startswith("tg://")
        )

    def _append_explanation(
        self,
        value: str | None,
        addition: str,
    ) -> str:
        if value is None or not value.strip():
            return addition

        if addition in value:
            return value

        return f"{value.strip()} {addition}"

    def _read_confidence(
        self,
        value: Any,
    ) -> float:
        if isinstance(value, int | float):
            return float(value)

        return 0.0

    def _deduplicate_strings(
        self,
        values: list[str],
    ) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            normalized = value.strip()

            if not normalized:
                continue

            key = normalized.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(normalized)

        return result
    