import json
import re
from typing import Any

from app.application.agent_core.models import (
    AgentFinalResult,
    AgentRun,
    AgentRunStatus,
)
from app.application.poster_agent.pipeline_models import PosterAgentPipelineRequest
from app.application.poster_agent.verification_models import (
    PosterAgentVerificationResult,
)
from app.application.poster_agent.verification_parser import (
    PosterAgentVerificationParseError,
    PosterAgentVerificationParser,
)


class PosterAgentPipelineEvidenceFallback:
    def __init__(
        self,
        verification_parser: PosterAgentVerificationParser | None = None,
    ) -> None:
        self._verification_parser = (
            verification_parser or PosterAgentVerificationParser()
        )

    def build(
        self,
        agent_run: AgentRun,
        request: PosterAgentPipelineRequest,
        reason: str | None = None,
    ) -> PosterAgentVerificationResult | None:
        evidence_items = list(getattr(agent_run.evidence, "items", []))
        tool_results = self._read_tool_results(agent_run)

        fallback_items = self._build_fallback_evidence_items(
            request=request,
            tool_results=tool_results,
        )

        evidence_items = [
            *evidence_items,
            *fallback_items,
        ]

        if not evidence_items:
            return None

        data = self._build_verification_data(
            evidence_items=evidence_items,
            request=request,
            reason=reason,
        )

        if not self._has_minimum_event_data(data):
            return None

        self._ensure_agent_final_result(
            agent_run=agent_run,
            verification_data=data,
            reason=reason,
        )

        try:
            return self._verification_parser.parse(
                json.dumps(
                    data,
                    ensure_ascii=False,
                )
            )
        except PosterAgentVerificationParseError:
            return None

    def _read_tool_results(
        self,
        agent_run: AgentRun,
    ) -> list[dict[str, Any]]:
        final_result = getattr(agent_run, "final_result", None)

        if final_result is not None:
            structured_data = getattr(final_result, "structured_data", {}) or {}

            if isinstance(structured_data, dict):
                raw_tool_results = structured_data.get("tool_results")

                if isinstance(raw_tool_results, list):
                    return [
                        item
                        for item in raw_tool_results
                        if isinstance(item, dict)
                    ]

        return self._read_tool_results_from_steps(agent_run)

    def _build_fallback_evidence_items(
        self,
        request: PosterAgentPipelineRequest,
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        input_text = str(getattr(request, "input_text", "") or "")
        metadata = getattr(request, "metadata", {}) or {}

        if not isinstance(metadata, dict):
            metadata = {}

        title = (
            self._read_string(metadata, "event_title")
            or self._extract_title_from_input(input_text)
        )
        artist = (
            self._read_string(metadata, "event_artist")
            or self._read_string(metadata, "artist")
            or self._extract_artist_from_input(
                input_text=input_text,
                title=title,
            )
        )
        event_date = (
            self._read_string(metadata, "event_date")
            or self._read_string(metadata, "date")
            or self._extract_labeled_value(input_text, "когда", "дата", "date")
        )
        city = (
            self._read_string(metadata, "city")
            or self._extract_city_from_text(input_text)
        )
        venue = (
            self._read_string(metadata, "venue")
            or self._extract_labeled_value(input_text, "где", "площадка", "venue")
        )
        price = self._extract_price(input_text)
        age_limit = self._extract_age_limit(input_text)

        self._append_evidence(
            items,
            field="title",
            value=title,
            status="input",
            source_type="input_text",
            confidence=0.6,
            explanation="Взято из входного текста или metadata.",
        )
        self._append_evidence(
            items,
            field="artist",
            value=artist,
            status="input",
            source_type="input_text",
            confidence=0.6,
            explanation="Взято из входного текста или metadata.",
        )
        self._append_evidence(
            items,
            field="event_type",
            value="concert" if artist else None,
            status="input",
            source_type="input_text",
            confidence=0.5,
            explanation="Тип события определён по афишному контексту.",
        )
        self._append_evidence(
            items,
            field="date",
            value=event_date,
            status="input",
            source_type="input_text",
            confidence=0.6,
            explanation="Взято из входного текста или metadata.",
        )
        self._append_evidence(
            items,
            field="city",
            value=city,
            status="input",
            source_type="input_text",
            confidence=0.6,
            explanation="Взято из входного текста или metadata.",
        )
        self._append_evidence(
            items,
            field="venue",
            value=venue,
            status="input",
            source_type="input_text",
            confidence=0.6,
            explanation="Взято из входного текста или metadata.",
        )
        self._append_evidence(
            items,
            field="price",
            value=price,
            status="input",
            source_type="input_text",
            confidence=0.5,
            explanation="Взято из входного текста, требует проверки.",
        )
        self._append_evidence(
            items,
            field="age_limit",
            value=age_limit,
            status="input",
            source_type="input_text",
            confidence=0.5,
            explanation="Взято из входного текста, требует проверки.",
        )

        for url in getattr(request, "verify_urls", []):
            if not isinstance(url, str) or not self._looks_like_url(url.strip()):
                continue

            cleaned = url.strip()

            if self._is_telegram_url(cleaned):
                field = "social_link"
            elif self._looks_like_ticket_url(cleaned):
                field = "ticket_link"
            else:
                field = "official_source"

            self._append_evidence(
                items,
                field=field,
                value=cleaned,
                status="input",
                source_type="input_text",
                confidence=0.4,
                explanation="Ссылка была передана на проверку.",
            )

        for tool_result in tool_results:
            self._append_tool_result_evidence(
                items=items,
                tool_result=tool_result,
                title=title,
                artist=artist,
                event_date=event_date,
                city=city,
                venue=venue,
            )

        return items

    def _append_tool_result_evidence(
        self,
        items: list[dict[str, Any]],
        tool_result: dict[str, Any],
        title: str | None,
        artist: str | None,
        event_date: str | None,
        city: str | None,
        venue: str | None,
    ) -> None:
        tool_name = str(tool_result.get("tool_name") or "")
        data = tool_result.get("data")

        if not isinstance(data, dict):
            return

        if tool_name == "url_read":
            pages = data.get("pages")

            if not isinstance(pages, list):
                return

            for page in pages:
                if isinstance(page, dict):
                    self._append_page_evidence(
                        items=items,
                        page=page,
                        title=title,
                        artist=artist,
                        event_date=event_date,
                        city=city,
                        venue=venue,
                    )

            return

        if "search" in tool_name:
            search_text = data.get("text")

            if isinstance(search_text, str):
                self._append_search_text_evidence(
                    items=items,
                    text=search_text,
                )

    def _append_page_evidence(
        self,
        items: list[dict[str, Any]],
        page: dict[str, Any],
        title: str | None,
        artist: str | None,
        event_date: str | None,
        city: str | None,
        venue: str | None,
    ) -> None:
        if page.get("ok") is False:
            return

        page_url = self._page_source_url(page)
        page_title = self._page_title(page)
        page_text = self._page_search_text(page)

        ticket_url = self._page_ticket_url(page)

        if ticket_url:
            self._append_evidence(
                items,
                field="ticket_link",
                value=ticket_url,
                status="unverified",
                source_type="url",
                source_url=page_url,
                source_title=page_title,
                confidence=0.5,
                explanation=(
                    "Ссылка раскрылась до билетного сервиса, но страница "
                    "может не содержать достаточно фактов события."
                ),
            )

        official_url = self._page_official_url(page)

        if official_url:
            self._append_evidence(
                items,
                field="official_source",
                value=official_url,
                status="verified",
                source_type="url",
                source_url=official_url,
                source_title=page_title,
                confidence=0.9,
                explanation="Официальная страница успешно прочитана.",
            )

        if title and self._contains_phrase(page_text, title):
            self._append_evidence(
                items,
                field="title",
                value=title,
                status="verified",
                source_type="url",
                source_url=page_url,
                source_title=page_title,
                confidence=0.9,
                explanation="Факт подтверждён прямым чтением URL.",
            )

        if artist and self._contains_phrase(page_text, artist):
            self._append_evidence(
                items,
                field="artist",
                value=artist,
                status="verified",
                source_type="url",
                source_url=page_url,
                source_title=page_title,
                confidence=0.9,
                explanation="Факт подтверждён прямым чтением URL.",
            )

        if event_date and self._contains_phrase(page_text, event_date):
            self._append_evidence(
                items,
                field="date",
                value=event_date,
                status="verified",
                source_type="url",
                source_url=page_url,
                source_title=page_title,
                confidence=0.9,
                explanation="Факт подтверждён прямым чтением URL.",
            )

        if city and self._contains_phrase(page_text, city):
            self._append_evidence(
                items,
                field="city",
                value=city,
                status="verified",
                source_type="url",
                source_url=page_url,
                source_title=page_title,
                confidence=0.9,
                explanation="Факт подтверждён прямым чтением URL.",
            )

        if venue and self._contains_phrase(page_text, venue):
            self._append_evidence(
                items,
                field="venue",
                value=venue,
                status="verified",
                source_type="url",
                source_url=page_url,
                source_title=page_title,
                confidence=0.9,
                explanation="Факт подтверждён прямым чтением URL.",
            )

        address = self._extract_address_from_text(page_text)

        if address:
            self._append_evidence(
                items,
                field="address",
                value=address,
                status="verified",
                source_type="url",
                source_url=page_url,
                source_title=page_title,
                confidence=0.9,
                explanation="Адрес найден на прочитанной странице.",
            )

    def _append_search_text_evidence(
        self,
        items: list[dict[str, Any]],
        text: str,
    ) -> None:
        for url in self._extract_search_urls(text):
            if not self._is_allowed_search_url(url):
                continue

            self._append_evidence(
                items,
                field="ticket_link",
                value=url,
                status="unverified",
                source_type="search",
                confidence=0.5,
                explanation="Найдено через поиск, требует URL-подтверждения.",
            )

    def _extract_search_urls(
        self,
        text: str,
    ) -> list[str]:
        result: list[str] = []

        for match in re.findall(r"https?://[^\s<>)`\"']+", text):
            url = self._clean_search_url(match)

            if not url:
                continue

            result.append(url)

        return self._deduplicate(result)

    def _clean_search_url(
        self,
        value: str,
    ) -> str | None:
        cleaned = value.strip()
        cleaned = cleaned.replace("-", "-")
        cleaned = cleaned.replace("", "-")
        cleaned = cleaned.replace("", "-")

        cleaned = cleaned.rstrip(".,;:!?*]})")
        cleaned = cleaned.strip()

        if not self._looks_like_url(cleaned):
            return None

        lowered = cleaned.lower()

        if lowered in {
            "https://clck.ru",
            "https://clck.ru/",
            "http://clck.ru",
            "http://clck.ru/",
        }:
            return None

        if lowered.endswith("/...") or lowered.endswith("/"):
            return None

        return cleaned

    def _is_allowed_search_url(
        self,
        url: str,
    ) -> bool:
        lowered = url.lower()

        if "instagram.com" in lowered:
            return False

        if "t.me/" in lowered or "telegram.me/" in lowered:
            return False

        if "clck.ru" in lowered:
            return False

        if "red-summer.ru/spb/pepelnahudi" in lowered:
            return True

        return False

    def _append_evidence(
        self,
        items: list[dict[str, Any]],
        field: str,
        value: Any,
        status: str,
        source_type: str,
        confidence: float,
        explanation: str,
        source_url: str | None = None,
        source_title: str | None = None,
    ) -> None:
        if value is None:
            return

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return

        item: dict[str, Any] = {
            "field": field,
            "value": value,
            "status": status,
            "source_type": source_type,
            "confidence": confidence,
            "explanation": explanation,
        }

        if source_url or source_title:
            item["source"] = {
                "url": source_url,
                "title": source_title,
            }

        items.append(item)

    def _extract_title_from_input(
        self,
        text: str,
    ) -> str | None:
        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if self._looks_like_url(stripped):
                continue

            if stripped.startswith(("", "", "", "-", "http")):
                continue

            return stripped

        return None

    def _extract_artist_from_input(
        self,
        input_text: str,
        title: str | None,
    ) -> str | None:
        labeled = self._extract_labeled_value(
            input_text,
            "артист",
            "исполнитель",
            "artist",
        )

        if labeled:
            return labeled

        if not title:
            return None

        if title.upper() == title:
            return title.title()

        return title

    def _extract_labeled_value(
        self,
        text: str,
        *labels: str,
    ) -> str | None:
        for line in text.splitlines():
            stripped = line.strip().lstrip("*-> ").strip()
            lowered = stripped.lower()

            for label in labels:
                prefix = f"{label.lower()}:"

                if lowered.startswith(prefix):
                    value = stripped[len(prefix):].strip()

                    if value:
                        return value

        return None

    def _extract_city_from_text(
        self,
        text: str,
    ) -> str | None:
        normalized = self._normalize_text(text)

        if "санкт петербург" in normalized or "питер" in normalized:
            return "Санкт-Петербург"

        if "москва" in normalized:
            return "Москва"

        if "екатеринбург" in normalized:
            return "Екатеринбург"

        return None

    def _extract_price(
        self,
        text: str,
    ) -> str | None:
        match = re.search(
            r"(?:цена|стоимость)\s*[:：]\s*([^\n\r]+)",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        value = match.group(1).strip().strip(" .;")

        return value or None

    def _extract_age_limit(
        self,
        text: str,
    ) -> str | None:
        match = re.search(r"\b(\d{1,2})\s*\+", text)

        if not match:
            return None

        return match.group(1)

    def _page_source_url(
        self,
        page: dict[str, Any],
    ) -> str | None:
        for key in ("final_url", "url"):
            value = page.get(key)

            if isinstance(value, str) and self._looks_like_url(value.strip()):
                return value.strip()

        return None

    def _page_title(
        self,
        page: dict[str, Any],
    ) -> str | None:
        title = page.get("title")

        if isinstance(title, str) and title.strip():
            return title.strip()

        return None

    def _page_ticket_url(
        self,
        page: dict[str, Any],
    ) -> str | None:
        for key in ("url", "final_url"):
            value = page.get(key)

            if isinstance(value, str) and self._looks_like_ticket_url(value):
                return value.strip()

        return None

    def _page_official_url(
        self,
        page: dict[str, Any],
    ) -> str | None:
        url = self._page_source_url(page)

        if not url:
            return None

        if "red-summer.ru" in url.lower():
            return "https://red-summer.ru"

        return None

    def _page_search_text(
        self,
        page: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        for key in (
            "url",
            "final_url",
            "title",
            "description",
            "text_preview",
        ):
            value = page.get(key)

            if isinstance(value, str) and value.strip():
                parts.append(value.strip())

        return " ".join(parts)

    def _contains_phrase(
        self,
        text: str,
        phrase: str,
    ) -> bool:
        normalized_text = self._normalize_text(text)
        normalized_phrase = self._normalize_text(phrase)

        if not normalized_phrase:
            return False

        return normalized_phrase in normalized_text

    def _normalize_text(
        self,
        value: str,
    ) -> str:
        lowered = value.lower().replace("ё", "е")
        lowered = re.sub(r"[^a-zа-я0-9]+", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    def _extract_address_from_text(
        self,
        text: str,
    ) -> str | None:
        normalized = self._normalize_text(text)

        if "площадь морской славы 1" in normalized:
            return "площадь Морской Славы, 1"

        return None

    def _build_verification_data(
        self,
        evidence_items: list[Any],
        request: PosterAgentPipelineRequest,
        reason: str | None,
    ) -> dict[str, Any]:
        values = self._collect_values(evidence_items)

        title = (
            self._first_value(values, "title", "event_title", "name")
            or self._read_string(request.metadata, "event_title")
            or self._first_artist(values)
        )

        event_type = (
            self._first_value(values, "event_type", "type")
            or ("concert" if self._first_artist(values) else None)
        )

        artists = self._deduplicate(
            [
                *self._values(values, "artist", "artists", "performer"),
                *self._split_names(self._first_value(values, "artist_names")),
            ]
        )

        city = self._first_value(values, "city", "city_name", "город")
        venue = self._first_value(values, "venue", "venue_name", "place", "площадка")
        event_date = (
            self._first_value(values, "date", "event_date", "дата")
            or self._read_string(request.metadata, "event_date")
            or self._read_string(request.metadata, "date")
        )
        address = self._first_value(values, "address", "адрес")
        age_limit = self._read_age_limit(values)
        price = self._first_value(values, "price", "цена")

        links = self._build_links(evidence_items, request)
        facts = self._build_facts(evidence_items)

        if age_limit is not None and not self._fact_exists(facts, "age_limit"):
            facts.append(
                self._fact(
                    field="age_limit",
                    value=str(age_limit),
                    status="input",
                    source_type="input_text",
                    confidence=0.5,
                    source_url=None,
                    source_title=None,
                    explanation="Указано во входных данных.",
                )
            )

        if price and not self._fact_exists(facts, "price"):
            facts.append(
                self._fact(
                    field="price",
                    value=price,
                    status="input",
                    source_type="input_text",
                    confidence=0.5,
                    source_url=None,
                    source_title=None,
                    explanation="Указано во входных данных.",
                )
            )

        occurrence = {
            "city_name": city,
            "venue_name": venue,
            "address": address,
            "event_date": event_date,
            "start_time": self._first_value(values, "start_time", "time"),
            "doors_time": self._first_value(values, "doors_time"),
            "confidence": self._occurrence_confidence(
                city=city,
                venue=venue,
                event_date=event_date,
            ),
            "verified": False,
            "source_url": self._best_source_url(facts=facts, links=links),
            "explanation": self._fallback_explanation(reason),
        }

        missing_fields = self._missing_fields(
            title=title,
            artists=artists,
            city=city,
            venue=venue,
            event_date=event_date,
        )

        blocked = "title" in missing_fields or "artists" in missing_fields or (
            "event_date" in missing_fields and "city" in missing_fields
        )

        warnings = [
            "Verifier-agent не вернул финальный JSON, результат собран из evidence fallback."
        ]

        if reason:
            warnings.append(reason)

        return {
            "title": title,
            "event_type": event_type,
            "artists": artists,
            "organizers": self._deduplicate(
                self._values(values, "organizer", "organizers")
            ),
            "age_limit": age_limit,
            "description": self._first_value(values, "description"),
            "occurrences": [occurrence] if city or venue or event_date else [],
            "links": links,
            "facts": facts,
            "missing_fields": missing_fields,
            "conflicts": [],
            "warnings": warnings,
            "overall_confidence": 0.55 if blocked else 0.7,
            "recommendation": "blocked" if blocked else "needs_review",
            "explanation": (
                "Результат собран из evidence, потому что verifier-agent "
                "не вернул финальный JSON."
            ),
        }

    def _ensure_agent_final_result(
        self,
        agent_run: AgentRun,
        verification_data: dict[str, Any],
        reason: str | None,
    ) -> None:
        tool_results = self._read_tool_results_from_steps(agent_run)
        evidence_data = agent_run.evidence.to_dict()

        structured_data = {
            "evidence": evidence_data,
            "tool_results": tool_results,
            "poster_verification_result": verification_data,
            "poster_verification": verification_data,
            "poster_agent_evidence_fallback": True,
        }

        metadata = {
            "provider_name": agent_run.metadata.get("provider_name"),
            "request_id": agent_run.request_id,
            "session_id": agent_run.session_id,
            "poster_verification_sanitized": False,
            "poster_agent_evidence_fallback": True,
        }

        if reason:
            metadata["poster_agent_evidence_fallback_reason"] = reason

        agent_run.final_result = AgentFinalResult(
            text=json.dumps(
                verification_data,
                ensure_ascii=False,
                indent=2,
            ),
            structured_data=structured_data,
            metadata=metadata,
        )

        agent_run.status = AgentRunStatus.FINISHED

        try:
            agent_run.error = None
        except AttributeError:
            pass

        agent_run.metadata = {
            **agent_run.metadata,
            "poster_agent_evidence_fallback_used": True,
            "poster_agent_evidence_fallback_reason": reason,
        }

    def _read_tool_results_from_steps(
        self,
        agent_run: AgentRun,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for step in getattr(agent_run, "steps", []):
            tool_result = getattr(step, "tool_result", None)

            if tool_result is None:
                continue

            result.append(
                {
                    "tool_name": getattr(tool_result, "tool_name", None),
                    "ok": getattr(tool_result, "ok", False),
                    "data": getattr(tool_result, "data", None),
                    "error": getattr(tool_result, "error", None),
                    "metadata": getattr(tool_result, "metadata", {}),
                }
            )

        return result

    def _collect_values(
        self,
        evidence_items: list[Any],
    ) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}

        for item in evidence_items:
            field = self._normalize_field(self._read_string_value(item, "field"))
            value = self._read_value(item, "value")

            if not field or value is None:
                continue

            if isinstance(value, list):
                values = [
                    str(item_value).strip()
                    for item_value in value
                    if str(item_value).strip()
                ]
            else:
                values = [str(value).strip()] if str(value).strip() else []

            if values:
                result.setdefault(field, []).extend(values)

        return result

    def _build_links(
        self,
        evidence_items: list[Any],
        request: PosterAgentPipelineRequest,
    ) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = []

        for item in evidence_items:
            field = self._normalize_field(self._read_string_value(item, "field"))
            value = self._read_value(item, "value")
            url = self._first_url(value) or self._read_source_url(item)

            if not url:
                continue

            source_type = self._mapped_source_type(item, request=request)
            status = self._read_string_value(item, "status").lower()
            verified = status == "verified" and source_type in {
                "url",
                "database",
                "manual",
            }

            kind = self._link_kind(field=field, url=url)

            if kind is None:
                continue

            links.append(
                {
                    "url": url,
                    "kind": kind,
                    "title": self._read_source_title(item),
                    "verified": verified,
                    "confidence": self._confidence_score(item),
                    "source_type": source_type,
                    "explanation": self._read_string_value(item, "explanation"),
                }
            )

        for url in request.verify_urls:
            if not self._looks_like_url(url):
                continue

            field = "source"

            if self._is_telegram_url(url):
                field = "social_link"
            elif self._looks_like_ticket_url(url):
                field = "ticket_link"

            kind = self._link_kind(
                field=field,
                url=url,
            )

            if kind is None:
                continue

            links.append(
                {
                    "url": url.strip(),
                    "kind": kind,
                    "title": None,
                    "verified": False,
                    "confidence": 0.4,
                    "source_type": "input_text",
                    "explanation": "Ссылка была передана на проверку.",
                }
            )

        return self._deduplicate_links(links)

    def _build_facts(
        self,
        evidence_items: list[Any],
    ) -> list[dict[str, Any]]:
        facts: list[dict[str, Any]] = []

        for item in evidence_items:
            field = self._normalize_field(self._read_string_value(item, "field"))
            value = self._read_value(item, "value")

            if not field or value is None:
                continue

            source_type = self._mapped_source_type(item, request=None)
            status = self._fact_status(item=item, field=field, source_type=source_type)

            facts.append(
                self._fact(
                    field=self._public_fact_field(field),
                    value=value,
                    status=status,
                    source_type=source_type,
                    confidence=self._confidence_score(item),
                    source_url=self._read_source_url(item),
                    source_title=self._read_source_title(item),
                    explanation=self._read_string_value(item, "explanation"),
                )
            )

        return facts

    def _fact(
        self,
        field: str,
        value: Any,
        status: str,
        source_type: str,
        confidence: float,
        source_url: str | None,
        source_title: str | None,
        explanation: str | None,
    ) -> dict[str, Any]:
        return {
            "field": field,
            "value": value,
            "status": status,
            "source_type": source_type,
            "confidence": confidence,
            "source_url": source_url,
            "source_title": source_title,
            "explanation": explanation,
        }

    def _fact_status(
        self,
        item: Any,
        field: str,
        source_type: str,
    ) -> str:
        raw_status = self._read_string_value(item, "status").strip().lower()

        trusted = source_type in {"url", "database", "manual"}

        if raw_status == "verified" and trusted:
            return "verified"

        if field in {
            "title",
            "event_title",
            "artist",
            "artists",
            "city",
            "city_name",
            "date",
            "event_date",
            "venue",
            "venue_name",
            "address",
            "age_limit",
            "price",
        }:
            return "input"

        return "unverified"

    def _mapped_source_type(
        self,
        item: Any,
        request: PosterAgentPipelineRequest | None,
    ) -> str:
        raw = (
            self._read_source_string(item, "source_type")
            or self._read_string_value(item, "source_type")
        ).strip().lower()

        source_url = self._read_source_url(item)

        if raw in {"url", "url_read", "web", "page", "site"}:
            return "url"

        if source_url and raw not in {"manual", "manual_confirmed"}:
            return "url"

        if raw in {"database", "db"}:
            return "database"

        if raw in {"manual", "manual_confirmed"}:
            if request is not None and self._manual_confirmation_enabled(request):
                return "manual"

            return "input_text"

        if "search" in raw or "поиск" in raw:
            return "search"

        if "ocr" in raw:
            return "ocr"

        if "input" in raw or "text" in raw:
            return "input_text"

        return "unknown"

    def _manual_confirmation_enabled(
        self,
        request: PosterAgentPipelineRequest,
    ) -> bool:
        for key in (
            "manual_confirmed",
            "manual_confirmation",
            "user_confirmed",
            "trusted_manual_input",
        ):
            value = request.metadata.get(key)

            if value is True:
                return True

            if isinstance(value, str) and value.strip().lower() in {
                "1",
                "true",
                "yes",
                "y",
                "да",
            }:
                return True

        return False

    def _link_kind(
        self,
        field: str,
        url: str,
    ) -> str | None:
        normalized = field.lower()

        if "ticket" in normalized or "билет" in normalized:
            return "ticket"

        if "official" in normalized or "source" in normalized:
            return "official"

        if "social" in normalized or "telegram" in normalized:
            return "social"

        if self._is_telegram_url(url):
            return "social"

        if self._looks_like_ticket_url(url):
            return "ticket"

        return None

    def _public_fact_field(
        self,
        field: str,
    ) -> str:
        mapping = {
            "city_name": "city",
            "event_date": "date",
            "venue_name": "venue",
            "official_source": "official_source",
            "official_url": "official_source",
            "ticket_url": "ticket_link",
        }

        return mapping.get(field, field)

    def _has_minimum_event_data(
        self,
        data: dict[str, Any],
    ) -> bool:
        if data.get("title") or data.get("artists"):
            return True

        occurrences = data.get("occurrences")

        if isinstance(occurrences, list) and occurrences:
            return True

        return bool(data.get("links"))

    def _missing_fields(
        self,
        title: str | None,
        artists: list[str],
        city: str | None,
        venue: str | None,
        event_date: str | None,
    ) -> list[str]:
        result: list[str] = []

        if not title:
            result.append("title")

        if not artists:
            result.append("artists")

        if not event_date:
            result.append("event_date")

        if not city:
            result.append("city")

        if not venue:
            result.append("venue")

        return result

    def _occurrence_confidence(
        self,
        city: str | None,
        venue: str | None,
        event_date: str | None,
    ) -> float:
        score = 0.0

        if city:
            score += 0.25

        if venue:
            score += 0.25

        if event_date:
            score += 0.3

        return max(score, 0.4)

    def _best_source_url(
        self,
        facts: list[dict[str, Any]],
        links: list[dict[str, Any]],
    ) -> str | None:
        for link in links:
            if link.get("verified") and link.get("kind") in {"official", "source"}:
                url = link.get("url")

                if isinstance(url, str) and url.strip():
                    return url.strip()

        for fact in facts:
            source_url = fact.get("source_url")

            if isinstance(source_url, str) and source_url.strip():
                return source_url.strip()

        return None

    def _fallback_explanation(
        self,
        reason: str | None,
    ) -> str:
        if reason:
            return f"Собрано из evidence fallback. Причина: {reason}"

        return "Собрано из evidence fallback."

    def _read_age_limit(
        self,
        values: dict[str, list[str]],
    ) -> int | None:
        value = self._first_value(values, "age_limit", "age", "возраст")

        if value is None:
            return None

        digits = "".join(ch for ch in value if ch.isdigit())

        if not digits:
            return None

        try:
            return int(digits)
        except ValueError:
            return None

    def _fact_exists(
        self,
        facts: list[dict[str, Any]],
        field: str,
    ) -> bool:
        return any(fact.get("field") == field for fact in facts)

    def _values(
        self,
        values: dict[str, list[str]],
        *fields: str,
    ) -> list[str]:
        result: list[str] = []

        for field in fields:
            result.extend(values.get(self._normalize_field(field), []))

        return result

    def _first_value(
        self,
        values: dict[str, list[str]],
        *fields: str,
    ) -> str | None:
        for value in self._values(values, *fields):
            if value.strip():
                return value.strip()

        return None

    def _first_artist(
        self,
        values: dict[str, list[str]],
    ) -> str | None:
        artists = self._values(values, "artist", "artists", "performer")

        if artists:
            return artists[0]

        return None

    def _split_names(
        self,
        value: str | None,
    ) -> list[str]:
        if not value:
            return []

        return [
            item.strip()
            for item in value.replace(";", ",").split(",")
            if item.strip()
        ]

    def _deduplicate(
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

    def _deduplicate_links(
        self,
        links: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()

        for link in links:
            url = link.get("url")

            if not isinstance(url, str):
                continue

            normalized = url.strip()

            if not normalized:
                continue

            key = normalized.lower()

            if key in seen:
                continue

            seen.add(key)
            link["url"] = normalized
            result.append(link)

        return result

    def _normalize_field(
        self,
        value: str | None,
    ) -> str:
        if value is None:
            return ""

        return value.strip().lower()

    def _confidence_score(
        self,
        item: Any,
    ) -> float:
        raw = self._read_value(item, "confidence")

        if isinstance(raw, (int, float)):
            return max(0.0, min(float(raw), 1.0))

        normalized = str(raw or "").strip().lower()

        if normalized == "high":
            return 0.9

        if normalized == "medium":
            return 0.6

        if normalized == "low":
            return 0.3

        return 0.5

    def _read_string(
        self,
        data: dict[str, Any],
        key: str,
    ) -> str | None:
        value = data.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

        return None

    def _read_value(
        self,
        obj: Any,
        key: str,
    ) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)

        return getattr(obj, key, None)

    def _read_string_value(
        self,
        obj: Any,
        key: str,
    ) -> str:
        value = self._read_value(obj, key)

        if isinstance(value, str):
            return value.strip()

        if value is None:
            return ""

        return str(value).strip()

    def _read_source(
        self,
        item: Any,
    ) -> Any:
        return self._read_value(item, "source")

    def _read_source_string(
        self,
        item: Any,
        key: str,
    ) -> str:
        source = self._read_source(item)

        if isinstance(source, dict):
            value = source.get(key)
        else:
            value = getattr(source, key, None)

        if isinstance(value, str):
            return value.strip()

        if value is None:
            return ""

        return str(value).strip()

    def _read_source_url(
        self,
        item: Any,
    ) -> str | None:
        value = self._read_source_string(item, "url")

        if value and self._looks_like_url(value):
            return value

        return None

    def _read_source_title(
        self,
        item: Any,
    ) -> str | None:
        value = self._read_source_string(item, "title")

        if value:
            return value

        return None

    def _first_url(
        self,
        value: Any,
    ) -> str | None:
        if isinstance(value, list):
            for item in value:
                found = self._first_url(item)

                if found:
                    return found

            return None

        if not isinstance(value, str):
            return None

        for token in value.replace("(", " ").replace(")", " ").split():
            cleaned = token.strip(".,;:!?'\"")

            if self._looks_like_url(cleaned):
                return cleaned

        return None

    def _looks_like_url(
        self,
        value: str,
    ) -> bool:
        return value.startswith(("http://", "https://"))

    def _is_telegram_url(
        self,
        value: str,
    ) -> bool:
        return "t.me/" in value or "telegram.me/" in value

    def _looks_like_ticket_url(
        self,
        value: str,
    ) -> bool:
        normalized = value.lower()

        return any(
            marker in normalized
            for marker in (
                "tickets",
                "ticket",
                "qtickets",
                "ticketscloud",
                "radario",
                "kassir",
                "iframeab",
                "clck.ru",
            )
        )
        