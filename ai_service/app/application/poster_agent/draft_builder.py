import re
from dataclasses import dataclass
from typing import Any

from app.application.agent_core import AgentRun
from app.application.poster_agent.models import (
    PosterAgentDraft,
    PosterAgentIssueSeverity,
    PosterAgentLink,
    PosterAgentLinkType,
    PosterAgentOccurrence,
    PosterAgentValidationIssue,
)


@dataclass(slots=True)
class PosterAgentDraftBuildRequest:
    agent_run: AgentRun


class PosterAgentDraftBuilder:
    def build(
        self,
        request: PosterAgentDraftBuildRequest,
    ) -> PosterAgentDraft:
        verification_data = self._get_verification_data(request.agent_run)

        if verification_data is not None:
            return self._build_from_verification_data(
                agent_run=request.agent_run,
                data=verification_data,
            )

        return self._build_from_legacy_data(request.agent_run)

    def _get_verification_data(
        self,
        agent_run: AgentRun,
    ) -> dict[str, Any] | None:
        if agent_run.final_result is None:
            return None

        value = agent_run.final_result.structured_data.get("poster_verification")

        if not isinstance(value, dict):
            return None

        return value

    def _build_from_verification_data(
        self,
        agent_run: AgentRun,
        data: dict[str, Any],
    ) -> PosterAgentDraft:
        return PosterAgentDraft(
            title=self._read_optional_string(data, "title"),
            event_type=self._read_optional_string(data, "event_type"),
            artists=self._read_string_list(data, "artists"),
            age_limit=self._read_optional_int(data, "age_limit"),
            description=self._read_optional_string(data, "description"),
            occurrences=self._read_occurrences(data),
            links=self._read_links(data),
            source_text=self._read_raw_agent_text(agent_run),
            validation_issues=self._build_validation_issues_from_verification_data(data),
            metadata={
                "source": "poster_verification",
                "organizers": self._read_string_list(data, "organizers"),
                "overall_confidence": self._read_float(data, "overall_confidence"),
                "recommendation": self._read_optional_string(data, "recommendation"),
                "missing_fields": self._read_string_list(data, "missing_fields"),
                "conflicts": self._read_string_list(data, "conflicts"),
                "warnings": self._read_string_list(data, "warnings"),
                "explanation": self._read_optional_string(data, "explanation"),
            },
        )

    def _read_occurrences(
        self,
        data: dict[str, Any],
    ) -> list[PosterAgentOccurrence]:
        value = data.get("occurrences")

        if not isinstance(value, list):
            return []

        result: list[PosterAgentOccurrence] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            result.append(
                PosterAgentOccurrence(
                    city=self._read_optional_string(item, "city_name"),
                    venue=self._read_optional_string(item, "venue_name"),
                    address=self._read_optional_string(item, "address"),
                    date=self._read_optional_string(item, "event_date"),
                    time=self._read_occurrence_time(item),
                    confidence=self._read_confidence_label(item),
                    verified=self._read_bool(item, "verified"),
                    metadata={
                        "source_url": self._read_optional_string(item, "source_url"),
                        "explanation": self._read_optional_string(item, "explanation"),
                        "start_time": self._read_optional_string(item, "start_time"),
                        "doors_time": self._read_optional_string(item, "doors_time"),
                        "confidence_score": self._read_float(item, "confidence"),
                    },
                )
            )

        return result

    def _read_links(
        self,
        data: dict[str, Any],
    ) -> list[PosterAgentLink]:
        value = data.get("links")

        if not isinstance(value, list):
            return []

        result: list[PosterAgentLink] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            url = self._read_optional_string(item, "url")

            if url is None:
                continue

            result.append(
                PosterAgentLink(
                    url=self._clean_url(url),
                    link_type=self._read_link_type(item),
                    title=self._read_optional_string(item, "title"),
                    verified=self._read_bool(item, "verified"),
                    source=self._read_optional_string(item, "source_type"),
                    metadata={
                        "confidence": self._read_float(item, "confidence"),
                        "explanation": self._read_optional_string(item, "explanation"),
                    },
                )
            )

        return result

    def _build_validation_issues_from_verification_data(
        self,
        data: dict[str, Any],
    ) -> list[PosterAgentValidationIssue]:
        issues: list[PosterAgentValidationIssue] = []

        for warning in self._read_string_list(data, "warnings"):
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.WARNING,
                    message=warning,
                )
            )

        for missing_field in self._read_string_list(data, "missing_fields"):
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.WARNING,
                    field=missing_field,
                    message=f"Не хватает поля: {missing_field}",
                )
            )

        for conflict in self._read_string_list(data, "conflicts"):
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.ERROR,
                    message=f"Конфликт: {conflict}",
                )
            )

        explanation = self._read_optional_string(data, "explanation")

        if explanation:
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.INFO,
                    message=explanation,
                )
            )

        return issues

    def _build_from_legacy_data(
        self,
        agent_run: AgentRun,
    ) -> PosterAgentDraft:
        raw_text = self._read_raw_agent_text(agent_run)

        return PosterAgentDraft(
            title=self._extract_title(raw_text),
            event_type=None,
            artists=self._extract_artists(raw_text),
            age_limit=self._extract_age_limit(raw_text),
            description=None,
            occurrences=self._extract_occurrences(raw_text),
            links=self._extract_links(raw_text),
            source_text=raw_text,
            validation_issues=self._extract_validation_issues(raw_text),
            metadata={
                "source": "legacy_text_parser",
            },
        )

    def _read_raw_agent_text(
        self,
        agent_run: AgentRun,
    ) -> str:
        if agent_run.final_result is None:
            return ""

        return agent_run.final_result.text or ""

    def _extract_title(
        self,
        text: str,
    ) -> str | None:
        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith("{"):
                continue

            if len(stripped) > 120:
                continue

            return stripped

        return None

    def _extract_artists(
        self,
        text: str,
    ) -> list[str]:
        result = []

        patterns = [
            r"артист(?:ы)?\s*:\s*(.+)",
            r"artist(?:s)?\s*:\s*(.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)

            if not match:
                continue

            result.extend(self._split_names(match.group(1)))

        return self._deduplicate_strings(result)

    def _extract_age_limit(
        self,
        text: str,
    ) -> int | None:
        match = re.search(r"\b(\d{1,2})\s*\+", text)

        if not match:
            return None

        return int(match.group(1))

    def _extract_occurrences(
        self,
        text: str,
    ) -> list[PosterAgentOccurrence]:
        result = []

        line_pattern = re.compile(
            r"(?P<date>\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?)"
            r".{0,80}?"
            r"(?P<city>[А-ЯЁA-Z][а-яёa-zA-ZА-ЯЁ -]{2,40})",
            flags=re.IGNORECASE,
        )

        for line in text.splitlines():
            match = line_pattern.search(line)

            if not match:
                continue

            result.append(
                PosterAgentOccurrence(
                    city=match.group("city").strip(),
                    date=match.group("date").strip(),
                    confidence="low",
                    verified=False,
                    metadata={
                        "raw_text": line.strip(),
                    },
                )
            )

        return result

    def _extract_links(
        self,
        text: str,
    ) -> list[PosterAgentLink]:
        urls = re.findall(
            r'https?://[^\s<>()\[\]{}"\'\\]+',
            text,
            flags=re.IGNORECASE,
        )

        return [
            PosterAgentLink(
                url=self._clean_url(url),
                link_type=PosterAgentLinkType.OTHER,
                verified=False,
                metadata={
                    "confidence": 0.3,
                },
            )
            for url in self._deduplicate_strings(urls)
        ]

    def _clean_url(
        self,
        url: str,
    ) -> str:
        value = url.split("\\n", 1)[0]
        value = value.split("\\r", 1)[0]
        value = value.split("\n", 1)[0]
        value = value.split("\r", 1)[0]

        return value.rstrip(".,;:!?)]}")

    def _extract_validation_issues(
        self,
        text: str,
    ) -> list[PosterAgentValidationIssue]:
        issues = []

        markers = [
            "не хватает",
            "не подтвержден",
            "не подтверждён",
            "conflict",
            "конфликт",
            "unverified",
        ]

        for line in text.splitlines():
            lowered = line.lower()

            if any(marker in lowered for marker in markers):
                issues.append(
                    PosterAgentValidationIssue(
                        severity=PosterAgentIssueSeverity.WARNING,
                        message=line.strip(),
                    )
                )

        return issues

    def _split_names(
        self,
        text: str,
    ) -> list[str]:
        return [
            item.strip()
            for item in re.split(r"[,;/|]", text)
            if item.strip()
        ]

    def _read_occurrence_time(
        self,
        data: dict[str, Any],
    ) -> str | None:
        return (
            self._read_optional_string(data, "start_time")
            or self._read_optional_string(data, "doors_time")
        )

    def _read_link_type(
        self,
        data: dict[str, Any],
    ) -> PosterAgentLinkType:
        value = self._read_optional_string(data, "kind")

        if value is None:
            return PosterAgentLinkType.OTHER

        normalized = value.lower()

        mapping = {
            "ticket": PosterAgentLinkType.TICKET,
            "tickets": PosterAgentLinkType.TICKET,
            "official": PosterAgentLinkType.OFFICIAL,
            "source": PosterAgentLinkType.SOURCE,
            "social": PosterAgentLinkType.SOCIAL,
        }

        return mapping.get(normalized, PosterAgentLinkType.OTHER)

    def _read_confidence_label(
        self,
        data: dict[str, Any],
    ) -> str | None:
        confidence = self._read_float(data, "confidence")

        if confidence >= 0.8:
            return "high"

        if confidence >= 0.5:
            return "medium"

        if confidence > 0:
            return "low"

        return None

    def _read_optional_string(
        self,
        data: dict[str, Any],
        key: str,
    ) -> str | None:
        value = data.get(key)

        if not isinstance(value, str):
            return None

        stripped = value.strip()

        if not stripped:
            return None

        return stripped

    def _read_string_list(
        self,
        data: dict[str, Any],
        key: str,
    ) -> list[str]:
        value = data.get(key)

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())

        return result

    def _read_optional_int(
        self,
        data: dict[str, Any],
        key: str,
    ) -> int | None:
        value = data.get(key)

        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())

        return None

    def _read_float(
        self,
        data: dict[str, Any],
        key: str,
    ) -> float:
        value = data.get(key)

        if isinstance(value, bool):
            return 0.0

        if isinstance(value, int | float):
            return self._clamp_confidence(float(value))

        if isinstance(value, str):
            try:
                return self._clamp_confidence(float(value.strip()))
            except ValueError:
                return 0.0

        return 0.0

    def _read_bool(
        self,
        data: dict[str, Any],
        key: str,
    ) -> bool:
        value = data.get(key)

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "1", "да"}

        return False

    def _clamp_confidence(
        self,
        value: float,
    ) -> float:
        if value < 0.0:
            return 0.0

        if value > 1.0:
            return 1.0

        return value

    def _deduplicate_strings(
        self,
        values: list[str],
    ) -> list[str]:
        result = []
        seen = set()

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
