from dataclasses import dataclass, field
from typing import Any

from app.application.agent_core.actions import AgentAction
from app.application.agent_core.tools import AgentToolOutput, AgentToolSpec


@dataclass(slots=True)
class AgentLoopToolCall:
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    expected_result: str | None = None
    output: AgentToolOutput | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "reason": self.reason,
            "expected_result": self.expected_result,
            "output": self.output.data if self.output is not None else None,
            "ok": self.output.ok if self.output is not None else None,
            "error": self.output.error if self.output is not None else None,
        }


@dataclass(slots=True)
class AgentLoopState:
    goal: str
    available_tools: list[AgentToolSpec]
    max_steps: int
    actions: list[AgentAction] = field(default_factory=list)
    tool_calls: list[AgentLoopToolCall] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)
    draft: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def step_count(
        self,
    ) -> int:
        return len(self.actions)

    @property
    def can_continue(
        self,
    ) -> bool:
        return self.step_count < self.max_steps

    def add_action(
        self,
        action: AgentAction,
    ) -> None:
        self.actions.append(action)

    def add_tool_call(
        self,
        action: AgentAction,
        output: AgentToolOutput,
    ) -> None:
        if action.tool_name is None:
            self.errors.append("Tool call action has no tool_name")
            return

        self.tool_calls.append(
            AgentLoopToolCall(
                tool_name=action.tool_name,
                arguments=action.arguments,
                reason=action.reason,
                expected_result=action.expected_result,
                output=output,
            )
        )

    def add_error(
        self,
        error: str,
    ) -> None:
        self.errors.append(error)

    def to_prompt_data(
        self,
    ) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "max_steps": self.max_steps,
            "step_count": self.step_count,
            "available_tools": [
                tool.to_dict()
                for tool in self.available_tools
                if tool.can_be_called_by_agent
            ],
            "tool_calls": [
                call.to_dict()
                for call in self.tool_calls
            ],
            "draft": self.draft,
            "notes": list(self.notes),
            "errors": list(self.errors),
        }
        



