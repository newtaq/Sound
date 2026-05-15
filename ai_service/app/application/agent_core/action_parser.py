import json
from typing import Any

from app.application.agent_core.action_enums import AgentActionType
from app.application.agent_core.actions import AgentAction


class AgentActionParseError(ValueError):
    pass


class AgentActionParser:
    def parse(
        self,
        text: str,
    ) -> AgentAction:
        data = self._load_json(text)

        if not isinstance(data, dict):
            raise AgentActionParseError("Agent action must be a JSON object")

        action_type = self._read_action_type(data)
        reason = self._read_reason(data)

        if action_type == AgentActionType.FINISH:
            return AgentAction.finish(reason=reason)

        if action_type == AgentActionType.TOOL_CALL:
            return AgentAction.tool_call(
                tool_name=self._read_tool_name(data),
                arguments=self._read_arguments(data),
                reason=reason,
                expected_result=self._read_optional_string(
                    data,
                    "expected_result",
                ),
            )

        raise AgentActionParseError(f"Unsupported agent action type: {action_type}")

    def _load_json(
        self,
        text: str,
    ) -> Any:
        prepared = self._strip_json_fence(text)

        try:
            return json.loads(prepared)
        except json.JSONDecodeError as error:
            raise AgentActionParseError(
                f"Invalid agent action JSON: {error}"
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

    def _read_action_type(
        self,
        data: dict[str, Any],
    ) -> AgentActionType:
        raw_value = data.get("action_type")

        if not isinstance(raw_value, str):
            raise AgentActionParseError("Field action_type must be a string")

        try:
            return AgentActionType(raw_value)
        except ValueError as error:
            raise AgentActionParseError(
                f"Unknown action_type: {raw_value}"
            ) from error

    def _read_reason(
        self,
        data: dict[str, Any],
    ) -> str:
        reason = data.get("reason")

        if not isinstance(reason, str) or not reason.strip():
            raise AgentActionParseError("Field reason must be a non-empty string")

        return reason.strip()

    def _read_tool_name(
        self,
        data: dict[str, Any],
    ) -> str:
        tool_name = data.get("tool_name")

        if not isinstance(tool_name, str) or not tool_name.strip():
            raise AgentActionParseError(
                "Field tool_name must be a non-empty string for tool_call"
            )

        return tool_name.strip()

    def _read_arguments(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        arguments = data.get("arguments", {})

        if arguments is None:
            return {}

        if not isinstance(arguments, dict):
            raise AgentActionParseError("Field arguments must be an object")

        return arguments

    def _read_optional_string(
        self,
        data: dict[str, Any],
        field_name: str,
    ) -> str | None:
        value = data.get(field_name)

        if value is None:
            return None

        if not isinstance(value, str):
            raise AgentActionParseError(f"Field {field_name} must be a string")

        stripped = value.strip()

        if not stripped:
            return None

        return stripped
    



