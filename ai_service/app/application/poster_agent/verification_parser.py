import json
from typing import Any

from app.application.poster_agent.verification_enums import (
    PosterAgentFactStatus,
    PosterAgentSourceType,
    PosterAgentVerificationRecommendation,
)
from app.application.poster_agent.verification_models import (
    PosterAgentVerificationFact,
    PosterAgentVerificationLink,
    PosterAgentVerificationOccurrence,
    PosterAgentVerificationResult,
)


class PosterAgentVerificationParseError(ValueError):
    pass


class PosterAgentVerificationParser:
    def parse(
        self,
        text: str,
    ) -> PosterAgentVerificationResult:
        data = self._load_json(text)

        if not isinstance(data, dict):
            raise PosterAgentVerificationParseError(
                "Poster verification result must be a JSON object"
            )

        return PosterAgentVerificationResult(
            title=self._read_optional_string(data, "title"),
            event_type=self._read_optional_string(data, "event_type"),
            artists=self._read_string_list(data, "artists"),
            organizers=self._read_string_list(data, "organizers"),
            age_limit=self._read_optional_int(data, "age_limit"),
            description=self._read_optional_string(data, "description"),
            occurrences=self._read_occurrences(data),
            links=self._read_links(data),
            facts=self._read_facts(data),
            missing_fields=self._read_string_list(data, "missing_fields"),
            conflicts=self._read_string_list(data, "conflicts"),
            warnings=self._read_string_list(data, "warnings"),
            overall_confidence=self._read_float(data, "overall_confidence"),
            recommendation=self._read_recommendation(data),
            explanation=self._read_optional_string(data, "explanation"),
        )

    def _load_json(
        self,
        text: str,
    ) -> Any:
        prepared = self._strip_json_fence(text)

        try:
            return json.loads(prepared)
        except json.JSONDecodeError as error:
            raise PosterAgentVerificationParseError(
                f"Invalid poster verification JSON: {error}"
            ) from error

    def _strip_json_fence(
        self,
        text: str,
    ) -> str:
        value = text.strip()

        if not value.startswith("```"):
            return value

        lines = value.splitlines()

        if len(lines) < 3:
            return value

        first_line = lines[0].strip().lower()
        last_line = lines[-1].strip()

        if first_line in {"```", "```json"} and last_line == "```":
            return "\n".join(lines[1:-1]).strip()

        return value

    def _read_occurrences(
        self,
        data: dict[str, Any],
    ) -> list[PosterAgentVerificationOccurrence]:
        value = data.get("occurrences")

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            if not isinstance(item, dict):
                continue

            result.append(
                PosterAgentVerificationOccurrence(
                    city_name=self._read_optional_string(item, "city_name"),
                    venue_name=self._read_optional_string(item, "venue_name"),
                    address=self._read_optional_string(item, "address"),
                    event_date=self._read_optional_string(item, "event_date"),
                    start_time=self._read_optional_string(item, "start_time"),
                    doors_time=self._read_optional_string(item, "doors_time"),
                    confidence=self._read_float(item, "confidence"),
                    verified=self._read_bool(item, "verified"),
                    source_url=self._read_optional_string(item, "source_url"),
                    explanation=self._read_optional_string(item, "explanation"),
                )
            )

        return result

    def _read_links(
        self,
        data: dict[str, Any],
    ) -> list[PosterAgentVerificationLink]:
        value = data.get("links")

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            if not isinstance(item, dict):
                continue

            url = self._read_optional_string(item, "url")

            if url is None:
                continue

            result.append(
                PosterAgentVerificationLink(
                    url=url,
                    kind=self._read_optional_string(item, "kind") or "unknown",
                    title=self._read_optional_string(item, "title"),
                    verified=self._read_bool(item, "verified"),
                    confidence=self._read_float(item, "confidence"),
                    source_type=self._read_source_type(item),
                    explanation=self._read_optional_string(item, "explanation"),
                )
            )

        return result

    def _read_facts(
        self,
        data: dict[str, Any],
    ) -> list[PosterAgentVerificationFact]:
        value = data.get("facts")

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            if not isinstance(item, dict):
                continue

            field = self._read_optional_string(item, "field")

            if field is None:
                continue

            result.append(
                PosterAgentVerificationFact(
                    field=field,
                    value=item.get("value"),
                    status=self._read_fact_status(item),
                    source_type=self._read_source_type(item),
                    confidence=self._read_float(item, "confidence"),
                    source_url=self._read_optional_string(item, "source_url"),
                    source_title=self._read_optional_string(item, "source_title"),
                    explanation=self._read_optional_string(item, "explanation"),
                )
            )

        return result

    def _read_fact_status(
        self,
        data: dict[str, Any],
    ) -> PosterAgentFactStatus:
        value = self._read_optional_string(data, "status")

        if value is None:
            return PosterAgentFactStatus.UNVERIFIED

        try:
            return PosterAgentFactStatus(value)
        except ValueError:
            return PosterAgentFactStatus.UNVERIFIED

    def _read_source_type(
        self,
        data: dict[str, Any],
    ) -> PosterAgentSourceType:
        value = self._read_optional_string(data, "source_type")

        if value is None:
            return PosterAgentSourceType.UNKNOWN

        normalized = value.strip().lower()

        aliases = {
            "input": PosterAgentSourceType.INPUT_TEXT,
            "input_text": PosterAgentSourceType.INPUT_TEXT,
            "source_text": PosterAgentSourceType.INPUT_TEXT,
            "ocr": PosterAgentSourceType.OCR,
            "qr": PosterAgentSourceType.QR,
            "url": PosterAgentSourceType.URL,
            "url_read": PosterAgentSourceType.URL,
            "url_parser": PosterAgentSourceType.URL,
            "link_parser": PosterAgentSourceType.URL,
            "search": PosterAgentSourceType.SEARCH,
            "groq_search": PosterAgentSourceType.SEARCH,
            "web_search": PosterAgentSourceType.SEARCH,
            "database": PosterAgentSourceType.DATABASE,
            "db": PosterAgentSourceType.DATABASE,
            "media_search": PosterAgentSourceType.MEDIA_SEARCH,
            "image_search": PosterAgentSourceType.MEDIA_SEARCH,
            "manual": PosterAgentSourceType.MANUAL,
            "unknown": PosterAgentSourceType.UNKNOWN,
        }

        return aliases.get(normalized, PosterAgentSourceType.UNKNOWN)

    def _read_recommendation(
        self,
        data: dict[str, Any],
    ) -> PosterAgentVerificationRecommendation:
        value = self._read_optional_string(data, "recommendation")

        if value is None:
            return PosterAgentVerificationRecommendation.NEEDS_REVIEW

        try:
            return PosterAgentVerificationRecommendation(value)
        except ValueError:
            return PosterAgentVerificationRecommendation.NEEDS_REVIEW

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

