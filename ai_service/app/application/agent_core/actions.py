from dataclasses import dataclass, field
from typing import Any

from app.application.agent_core.action_enums import AgentActionType


@dataclass(slots=True)
class AgentAction:
    action_type: AgentActionType
    reason: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    expected_result: str | None = None

    @classmethod
    def tool_call(
        cls,
        tool_name: str,
        arguments: dict[str, Any],
        reason: str,
        expected_result: str | None = None,
    ) -> "AgentAction":
        return cls(
            action_type=AgentActionType.TOOL_CALL,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            expected_result=expected_result,
        )

    @classmethod
    def finish(
        cls,
        reason: str,
    ) -> "AgentAction":
        return cls(
            action_type=AgentActionType.FINISH,
            reason=reason,
        )

    def is_tool_call(
        self,
    ) -> bool:
        return self.action_type == AgentActionType.TOOL_CALL

    def is_finish(
        self,
    ) -> bool:
        return self.action_type == AgentActionType.FINISH

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "reason": self.reason,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "expected_result": self.expected_result,
        }
        


