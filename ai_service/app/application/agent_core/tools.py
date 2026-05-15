from dataclasses import dataclass, field
from typing import Any, Protocol

from app.application.agent_core.tool_enums import (
    AgentToolCategory,
    AgentToolCostLevel,
    AgentToolTrustLevel,
)


@dataclass(slots=True)
class AgentToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    category: AgentToolCategory = AgentToolCategory.UTILITY
    capabilities: list[str] = field(default_factory=list)
    produces_evidence: bool = True
    trust_level: AgentToolTrustLevel = AgentToolTrustLevel.CANDIDATE
    cost_level: AgentToolCostLevel = AgentToolCostLevel.LOW
    can_run_automatically: bool = False
    can_be_called_by_agent: bool = True
    timeout_seconds: float | None = None

    def has_capability(
        self,
        capability: str,
    ) -> bool:
        return capability in self.capabilities

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "category": self.category.value,
            "capabilities": list(self.capabilities),
            "produces_evidence": self.produces_evidence,
            "trust_level": self.trust_level.value,
            "cost_level": self.cost_level.value,
            "can_run_automatically": self.can_run_automatically,
            "can_be_called_by_agent": self.can_be_called_by_agent,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(slots=True)
class AgentToolInput:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentToolOutput:
    tool_name: str
    ok: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentTool(Protocol):
    @property
    def spec(self) -> AgentToolSpec:
        raise NotImplementedError

    async def run(
        self,
        tool_input: AgentToolInput,
    ) -> AgentToolOutput:
        raise NotImplementedError


class AgentToolRegistry:
    def __init__(
        self,
        tools: list[AgentTool] | None = None,
    ) -> None:
        self._tools: dict[str, AgentTool] = {}

        for tool in tools or []:
            self.register(tool)

    def register(
        self,
        tool: AgentTool,
    ) -> None:
        self._tools[tool.spec.name] = tool

    def get(
        self,
        name: str,
    ) -> AgentTool:
        tool = self._tools.get(name)

        if tool is None:
            available = ", ".join(sorted(self._tools))
            raise ValueError(
                f"Unknown agent tool: {name}. Available tools: {available}"
            )

        return tool

    def list_specs(self) -> list[AgentToolSpec]:
        return [
            tool.spec
            for tool in self._tools.values()
        ]

    def list_specs_data(
        self,
    ) -> list[dict[str, Any]]:
        return [
            tool.spec.to_dict()
            for tool in self._tools.values()
        ]

    def find_by_category(
        self,
        category: AgentToolCategory,
    ) -> list[AgentTool]:
        return [
            tool
            for tool in self._tools.values()
            if tool.spec.category == category
        ]

    def find_by_capability(
        self,
        capability: str,
    ) -> list[AgentTool]:
        return [
            tool
            for tool in self._tools.values()
            if tool.spec.has_capability(capability)
        ]

    async def run(
        self,
        tool_input: AgentToolInput,
    ) -> AgentToolOutput:
        tool = self.get(tool_input.tool_name)

        return await tool.run(tool_input)
    


