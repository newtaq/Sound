from typing import Protocol

from app.application.agent_core.models import AgentRun


class AgentRunDebugSink(Protocol):
    def emit_agent_run(
        self,
        run: AgentRun,
    ) -> None:
        pass
