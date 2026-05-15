from dataclasses import dataclass, field

from app.application.contracts import AISqlPlanItem


@dataclass(slots=True)
class AISqlValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


class AISqlPlanValidator:
    _forbidden_words = (
        "drop",
        "alter",
        "truncate",
        "delete",
        "update",
        "create",
        "grant",
        "revoke",
        "execute",
    )

    _allowed_prefixes = (
        "insert into ai_",
        "select ",
    )

    def validate_item(self, item: AISqlPlanItem) -> AISqlValidationResult:
        sql = item.sql.strip()
        normalized = " ".join(sql.lower().split())

        errors: list[str] = []

        if not normalized:
            errors.append("SQL is empty")

        if not normalized.startswith(self._allowed_prefixes):
            errors.append("SQL must start with SELECT or INSERT INTO ai_*")

        for word in self._forbidden_words:
            if f" {word} " in f" {normalized} ":
                errors.append(f"Forbidden SQL keyword: {word}")

        if normalized.startswith("select ") and " limit " not in normalized:
            errors.append("SELECT query must contain LIMIT")

        return AISqlValidationResult(
            ok=not errors,
            errors=errors,
        )

    def validate_plan(self, plan: list[AISqlPlanItem]) -> AISqlValidationResult:
        errors: list[str] = []

        for index, item in enumerate(plan):
            result = self.validate_item(item)
            for error in result.errors:
                errors.append(f"sql_plan[{index}]: {error}")

        return AISqlValidationResult(
            ok=not errors,
            errors=errors,
        )
        

