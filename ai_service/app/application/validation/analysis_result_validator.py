from dataclasses import dataclass, field

from app.application.contracts import AIAnalysisResult


@dataclass(slots=True)
class AIAnalysisValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AIAnalysisResultValidator:
    def validate(self, result: AIAnalysisResult) -> AIAnalysisValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if result.confidence < 0 or result.confidence > 1:
            errors.append("confidence must be between 0 and 1")

        if result.content_type == "trash" and result.is_useful:
            errors.append("trash content cannot be useful")

        if result.priority == "trash" and result.is_useful:
            errors.append("trash priority cannot be useful")

        if result.content_type == "trash" and result.main_decision != "ignore":
            warnings.append("trash content should usually have main_decision=ignore")

        if result.is_useful and result.main_decision == "ignore":
            warnings.append("useful content should not usually have main_decision=ignore")

        if not result.decisions:
            warnings.append("decisions list is empty")

        decision_types = {decision.type for decision in result.decisions}

        if result.main_decision not in decision_types:
            warnings.append("main_decision is not present in decisions list")

        for index, decision in enumerate(result.decisions):
            if decision.confidence is not None and (
                decision.confidence < 0 or decision.confidence > 1
            ):
                errors.append(f"decisions[{index}].confidence must be between 0 and 1")

        if result.variants and result.confidence >= 0.95:
            warnings.append("high confidence result usually should not have variants")

        return AIAnalysisValidationResult(
            ok=not errors,
            errors=errors,
            warnings=warnings,
        )
        

