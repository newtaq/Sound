from dataclasses import dataclass, field
from typing import Any

from app.application.agent_core import AgentRun
from app.application.contracts import AIMedia, AIMode
from app.application.poster_agent.models import (
    PosterAgentDraft,
    PosterAgentPublishDecision,
)
from app.application.poster_agent.verification_models import (
    PosterAgentVerificationResult,
)


@dataclass(slots=True)
class PosterAgentPipelineRequest:
    input_text: str
    session_id: str | None = None
    provider_name: str | None = None
    mode: AIMode = AIMode.DEEP
    max_steps: int = 8
    use_search: bool = True
    use_url_read: bool = True
    adaptive_tools: bool = True
    structured_verification: bool = True
    search_query: str | None = None
    search_context: str | None = None
    verify_urls: list[str] = field(default_factory=list)
    media: list[AIMedia] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PosterAgentPipelineResult:
    agent_run: AgentRun
    draft: PosterAgentDraft
    decision: PosterAgentPublishDecision
    review_text: str
    post_text: str = ""
    event_summary_text: str = ""
    verification_result: PosterAgentVerificationResult | None = None
    verification_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": {
                "status": self.agent_run.status.value,
                "request_id": self.agent_run.request_id,
                "session_id": self.agent_run.session_id,
                "goal": self.agent_run.goal,
                "evidence": self.agent_run.evidence.to_dict(),
                "metadata": self.agent_run.metadata,
            },
            "draft": self.draft.to_dict(),
            "decision": self.decision.to_dict(),
            "verification_result": (
                self.verification_result.to_dict()
                if self.verification_result is not None
                else None
            ),
            "verification_error": self.verification_error,
            "review_text": self.review_text,
            "post_text": self.post_text,
            "event_summary_text": self.event_summary_text,
        }
        