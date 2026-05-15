from typing import Any

from app.application.contracts import (
    AIAnalysisResult,
    AIDecision,
    AIEvidence,
    AISqlPlanItem,
)


class AIAnalysisResultSerializer:
    def to_dict(self, result: AIAnalysisResult) -> dict[str, Any]:
        return {
            "content_type": result.content_type,
            "is_useful": result.is_useful,
            "priority": result.priority,
            "confidence": result.confidence,
            "main_decision": result.main_decision,
            "decisions": [
                self._decision_to_dict(decision)
                for decision in result.decisions
            ],
            "variants": result.variants,
            "sql_plan": [
                self._sql_plan_item_to_dict(item)
                for item in result.sql_plan
            ],
            "warnings": result.warnings,
            "raw": result.raw,
        }

    def from_dict(self, data: dict[str, Any]) -> AIAnalysisResult | None:
        try:
            content_type = data["content_type"]
            is_useful = data["is_useful"]
            priority = data["priority"]
            confidence = data["confidence"]
            main_decision = data["main_decision"]
        except KeyError:
            return None

        if not isinstance(content_type, str):
            return None

        if not isinstance(is_useful, bool):
            return None

        if not isinstance(priority, str):
            return None

        if not isinstance(main_decision, str):
            return None

        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            return None

        return AIAnalysisResult(
            content_type=content_type,
            is_useful=is_useful,
            priority=priority,
            confidence=confidence_value,
            main_decision=main_decision,
            decisions=self._decisions_from_value(data.get("decisions")),
            variants=self._list_of_dicts_from_value(data.get("variants")),
            sql_plan=self._sql_plan_from_value(data.get("sql_plan")),
            warnings=self._strings_from_value(data.get("warnings")),
            raw=self._dict_from_value(data.get("raw")),
        )

    def _decision_to_dict(self, decision: AIDecision) -> dict[str, Any]:
        return {
            "type": decision.type,
            "confidence": decision.confidence,
            "data": decision.data,
            "evidence": [
                self._evidence_to_dict(evidence)
                for evidence in decision.evidence
            ],
        }

    def _evidence_to_dict(self, evidence: AIEvidence) -> dict[str, Any]:
        return {
            "field": evidence.field,
            "value": evidence.value,
            "source": evidence.source,
            "source_text": evidence.source_text,
            "confidence": evidence.confidence,
            "metadata": evidence.metadata,
        }

    def _sql_plan_item_to_dict(self, item: AISqlPlanItem) -> dict[str, Any]:
        return {
            "sql": item.sql,
            "purpose": item.purpose,
            "confidence": item.confidence,
            "requires_review": item.requires_review,
            "metadata": item.metadata,
        }

    def _decisions_from_value(self, value: Any) -> list[AIDecision]:
        if not isinstance(value, list):
            return []

        result: list[AIDecision] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            decision_type = item.get("type")
            if not isinstance(decision_type, str):
                continue

            result.append(
                AIDecision(
                    type=decision_type,
                    confidence=self._optional_float_from_value(item.get("confidence")),
                    data=self._dict_from_value(item.get("data")),
                    evidence=self._evidence_from_value(item.get("evidence")),
                )
            )

        return result

    def _evidence_from_value(self, value: Any) -> list[AIEvidence]:
        if not isinstance(value, list):
            return []

        result: list[AIEvidence] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            field = item.get("field")
            if not isinstance(field, str):
                continue

            source = item.get("source")
            source_text = item.get("source_text")

            result.append(
                AIEvidence(
                    field=field,
                    value=item.get("value"),
                    source=source if isinstance(source, str) else None,
                    source_text=source_text if isinstance(source_text, str) else None,
                    confidence=self._optional_float_from_value(item.get("confidence")),
                    metadata=self._dict_from_value(item.get("metadata")),
                )
            )

        return result

    def _sql_plan_from_value(self, value: Any) -> list[AISqlPlanItem]:
        if not isinstance(value, list):
            return []

        result: list[AISqlPlanItem] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            sql = item.get("sql")
            if not isinstance(sql, str):
                continue

            purpose = item.get("purpose")

            result.append(
                AISqlPlanItem(
                    sql=sql,
                    purpose=purpose if isinstance(purpose, str) else None,
                    confidence=self._optional_float_from_value(item.get("confidence")),
                    requires_review=bool(item.get("requires_review", True)),
                    metadata=self._dict_from_value(item.get("metadata")),
                )
            )

        return result

    def _dict_from_value(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}

        result: dict[str, Any] = {}

        for key, item in value.items():
            if isinstance(key, str):
                result[key] = item

        return result

    def _list_of_dicts_from_value(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        return [
            self._dict_from_value(item)
            for item in value
            if isinstance(item, dict)
        ]

    def _strings_from_value(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        return [
            item
            for item in value
            if isinstance(item, str)
        ]

    def _optional_float_from_value(self, value: Any) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None
        

