from dataclasses import dataclass

from app.application.poster_agent.models import (
    PosterAgentDraft,
    PosterAgentDraftStatus,
    PosterAgentIssueSeverity,
    PosterAgentPublishDecision,
    PosterAgentValidationIssue,
)


@dataclass(slots=True)
class PosterPublishDecisionEngineConfig:
    auto_publish_confidence_threshold: float = 0.85
    review_confidence_threshold: float = 0.55
    require_verified_occurrence: bool = True
    require_verified_link: bool = True


class PosterPublishDecisionEngine:
    def __init__(
        self,
        config: PosterPublishDecisionEngineConfig | None = None,
    ) -> None:
        self._config = config or PosterPublishDecisionEngineConfig()

    def decide(
        self,
        draft: PosterAgentDraft,
        validation_decision: PosterAgentPublishDecision,
    ) -> PosterAgentPublishDecision:
        blocking_reasons = self._collect_blocking_reasons(draft)
        review_reasons = self._collect_review_reasons(
            draft=draft,
            validation_decision=validation_decision,
        )

        if blocking_reasons:
            return PosterAgentPublishDecision(
                can_publish=False,
                status=PosterAgentDraftStatus.BLOCKED,
                reason="Автопубликация запрещена: есть критические проблемы.",
                issues=[
                    *validation_decision.issues,
                    *self._build_issues(
                        messages=blocking_reasons,
                        severity=PosterAgentIssueSeverity.ERROR,
                    ),
                ],
                metadata={
                    "publish_status": "blocked",
                    "overall_confidence": self._read_overall_confidence(draft),
                },
            )

        overall_confidence = self._read_overall_confidence(draft)

        if (
            overall_confidence >= self._config.auto_publish_confidence_threshold
            and not review_reasons
        ):
            return PosterAgentPublishDecision(
                can_publish=True,
                status=PosterAgentDraftStatus.READY_TO_PUBLISH,
                reason="Черновик достаточно подтверждён для автоматической публикации.",
                issues=validation_decision.issues,
                metadata={
                    "publish_status": "auto_publish",
                    "overall_confidence": overall_confidence,
                },
            )

        return PosterAgentPublishDecision(
            can_publish=False,
            status=PosterAgentDraftStatus.NEEDS_REVIEW,
            reason="Черновик требует ручной проверки.",
            issues=[
                *validation_decision.issues,
                *self._build_issues(
                    messages=review_reasons,
                    severity=PosterAgentIssueSeverity.WARNING,
                ),
            ],
            metadata={
                "publish_status": "needs_review",
                "overall_confidence": overall_confidence,
            },
        )

    def _collect_blocking_reasons(
        self,
        draft: PosterAgentDraft,
    ) -> list[str]:
        reasons: list[str] = []

        if not draft.title:
            reasons.append("Нет названия события.")

        if not draft.occurrences:
            reasons.append("Нет ни одной даты/города события.")

        if draft.occurrences and not self._has_occurrence_with_date(draft):
            reasons.append("Нет даты события.")

        if draft.occurrences and not self._has_occurrence_with_city(draft):
            reasons.append("Нет города события.")

        conflicts = self._read_metadata_string_list(draft, "conflicts")

        for conflict in conflicts:
            reasons.append(f"Есть конфликт: {conflict}")

        return self._deduplicate_strings(reasons)

    def _collect_review_reasons(
        self,
        draft: PosterAgentDraft,
        validation_decision: PosterAgentPublishDecision,
    ) -> list[str]:
        reasons: list[str] = []

        if not validation_decision.can_publish:
            reasons.append(validation_decision.reason)

        if self._config.require_verified_occurrence and not self._has_verified_occurrence(draft):
            reasons.append("Нет подтверждённой даты/города события.")

        if self._config.require_verified_link and not self._has_verified_link(draft):
            reasons.append("Нет подтверждённой ссылки на билеты или официальный источник.")

        missing_fields = self._read_metadata_string_list(draft, "missing_fields")

        for field in missing_fields:
            reasons.append(f"Нужно проверить поле: {field}")

        recommendation = self._read_metadata_string(draft, "recommendation")

        if recommendation == "blocked":
            reasons.append("Verifier-agent рекомендовал blocked.")

        if recommendation == "needs_review":
            reasons.append("Verifier-agent рекомендовал ручную проверку.")

        overall_confidence = self._read_overall_confidence(draft)

        if overall_confidence < self._config.review_confidence_threshold:
            reasons.append("Низкая общая уверенность черновика.")

        return self._deduplicate_strings(reasons)

    def _build_issues(
        self,
        messages: list[str],
        severity: PosterAgentIssueSeverity,
    ) -> list[PosterAgentValidationIssue]:
        result = []

        for message in self._deduplicate_strings(messages):
            result.append(
                PosterAgentValidationIssue(
                    severity=severity,
                    message=message,
                    field="publish_decision",
                )
            )

        return result

    def _has_occurrence_with_date(
        self,
        draft: PosterAgentDraft,
    ) -> bool:
        return any(
            occurrence.date
            for occurrence in draft.occurrences
        )

    def _has_occurrence_with_city(
        self,
        draft: PosterAgentDraft,
    ) -> bool:
        return any(
            occurrence.city
            for occurrence in draft.occurrences
        )

    def _has_verified_occurrence(
        self,
        draft: PosterAgentDraft,
    ) -> bool:
        return any(
            occurrence.verified
            for occurrence in draft.occurrences
        )

    def _has_verified_link(
        self,
        draft: PosterAgentDraft,
    ) -> bool:
        return any(
            link.verified
            for link in draft.links
        )

    def _read_overall_confidence(
        self,
        draft: PosterAgentDraft,
    ) -> float:
        value = draft.metadata.get("overall_confidence")

        if isinstance(value, bool):
            return 0.0

        if isinstance(value, int | float):
            return self._clamp(float(value))

        if isinstance(value, str):
            try:
                return self._clamp(float(value.strip()))
            except ValueError:
                return 0.0

        return 0.0

    def _read_metadata_string(
        self,
        draft: PosterAgentDraft,
        key: str,
    ) -> str | None:
        value = draft.metadata.get(key)

        if not isinstance(value, str):
            return None

        stripped = value.strip()

        if not stripped:
            return None

        return stripped

    def _read_metadata_string_list(
        self,
        draft: PosterAgentDraft,
        key: str,
    ) -> list[str]:
        value = draft.metadata.get(key)

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())

        return result

    def _clamp(
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
