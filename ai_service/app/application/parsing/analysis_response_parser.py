import json
from typing import Any

from app.application.contracts import (
    AIAnalysisResult,
    AIContentRegistry,
    AIDecision,
    AIEvidence,
    AIParsedAnalysis,
    AIResponse,
    AISqlPlanItem,
)


class AnalysisResponseParser:
    def __init__(self, content_registry: AIContentRegistry | None = None) -> None:
        self._content_registry = content_registry or AIContentRegistry()

    def parse(self, response: AIResponse) -> AIParsedAnalysis:
        text = response.text.strip()
        json_text = self._extract_json_object_text(text)

        if json_text is None:
            return AIParsedAnalysis(
                ok=False,
                raw_text=response.text,
                error="JSON object was not found",
            )

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as error:
            return AIParsedAnalysis(
                ok=False,
                raw_text=response.text,
                error=f"Invalid JSON: {error}",
            )

        if not isinstance(data, dict):
            return AIParsedAnalysis(
                ok=False,
                raw_text=response.text,
                error="JSON root must be an object",
            )

        warnings: list[str] = []
        if json_text != text:
            warnings.append("Response contained extra text outside JSON object")

        return AIParsedAnalysis(
            ok=True,
            data=data,
            raw_text=response.text,
            warnings=warnings,
        )

    def parse_result(self, response: AIResponse) -> AIAnalysisResult | None:
        parsed = self.parse(response)

        if not parsed.ok or parsed.data is None:
            return None

        data = parsed.data

        content_type = data.get("content_type")
        priority = data.get("priority")
        main_decision = data.get("main_decision")

        if not isinstance(content_type, str):
            return None

        if not isinstance(priority, str):
            return None

        if not isinstance(main_decision, str):
            return None

        if content_type not in self._content_registry.content_types:
            return None

        if priority not in self._content_registry.priorities:
            return None

        if main_decision not in self._content_registry.decision_types:
            return None

        confidence = self._parse_confidence(data.get("confidence"))
        if confidence is None:
            return None

        result = AIAnalysisResult(
            content_type=content_type,
            is_useful=bool(data.get("is_useful")),
            priority=priority,
            confidence=confidence,
            main_decision=main_decision,
            decisions=self._parse_decisions(data.get("decisions"), main_decision),
            variants=list(data.get("variants") or []),
            sql_plan=self._parse_sql_plan(data.get("sql_plan")),
            warnings=list(data.get("warnings") or []),
            raw=data,
        )

        result.warnings.extend(parsed.warnings)

        return result

    def _extract_json_object_text(self, text: str) -> str | None:
        if not text:
            return None

        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(text)):
            char = text[index]

            if escaped:
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1
                continue

            if char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        return None

    def _parse_decisions(
        self,
        value: Any,
        main_decision: str,
    ) -> list[AIDecision]:
        if not isinstance(value, list):
            return [
                AIDecision(
                    type=main_decision,
                    confidence=1.0,
                    data={},
                )
            ]

        result: list[AIDecision] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            decision_type = item.get("type")
            if not isinstance(decision_type, str):
                continue

            if decision_type not in self._content_registry.decision_types:
                continue

            confidence = self._parse_optional_confidence(item.get("confidence"))

            data_value = item.get("data")
            data = data_value if isinstance(data_value, dict) else {}

            result.append(
                AIDecision(
                    type=decision_type,
                    confidence=confidence,
                    data=data,
                    evidence=self._parse_evidence(item.get("evidence")),
                )
            )

        return result

    def _parse_evidence(self, value: Any) -> list[AIEvidence]:
        if not isinstance(value, list):
            return []

        result: list[AIEvidence] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            field_value = item.get("field")
            if not isinstance(field_value, str) or not field_value.strip():
                continue

            source_value = item.get("source")
            source = source_value if isinstance(source_value, str) else None

            source_text_value = item.get("source_text")
            source_text = source_text_value if isinstance(source_text_value, str) else None

            metadata_value = item.get("metadata")
            metadata = metadata_value if isinstance(metadata_value, dict) else {}

            result.append(
                AIEvidence(
                    field=field_value.strip(),
                    value=item.get("value"),
                    source=source,
                    source_text=source_text,
                    confidence=self._parse_optional_confidence(item.get("confidence")),
                    metadata=metadata,
                )
            )

        return result

    def _parse_sql_plan(self, value: Any) -> list[AISqlPlanItem]:
        if not isinstance(value, list):
            return []

        result: list[AISqlPlanItem] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            sql = item.get("sql")
            if not isinstance(sql, str) or not sql.strip():
                continue

            confidence = self._parse_optional_confidence(item.get("confidence"))

            purpose_value = item.get("purpose")
            purpose = purpose_value if isinstance(purpose_value, str) else None

            metadata_value = item.get("metadata")
            metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}

            result.append(
                AISqlPlanItem(
                    sql=sql.strip(),
                    purpose=purpose,
                    confidence=confidence,
                    requires_review=bool(item.get("requires_review", True)),
                    metadata=metadata,
                )
            )

        return result

    def _parse_confidence(self, value: Any) -> float | None:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return None

        if confidence < 0 or confidence > 1:
            return None

        return confidence

    def _parse_optional_confidence(self, value: Any) -> float | None:
        if value is None:
            return None

        return self._parse_confidence(value)
    

