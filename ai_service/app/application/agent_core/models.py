from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.application.agent_core.evidence import AgentEvidenceSet


class AgentRunStatus(str, Enum):
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"
    NEEDS_INPUT = "needs_input"


class AgentStepType(str, Enum):
    THINK = "think"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL = "final"


@dataclass(slots=True)
class AgentToolCall:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentToolResult:
    tool_name: str
    ok: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentStep:
    index: int
    step_type: AgentStepType
    content: str = ""
    tool_call: AgentToolCall | None = None
    tool_result: AgentToolResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentPlan:
    goal: str
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentFinalResult:
    text: str
    structured_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentRun:
    session_id: str | None
    request_id: str | None
    status: AgentRunStatus
    goal: str
    plan: AgentPlan | None = None
    steps: list[AgentStep] = field(default_factory=list)
    evidence: AgentEvidenceSet = field(default_factory=AgentEvidenceSet)
    final_result: AgentFinalResult | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(
        self,
        step: AgentStep,
    ) -> None:
        self.steps.append(step)

    def next_step_index(self) -> int:
        return len(self.steps) + 1
    


