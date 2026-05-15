import json

from app.application.agent_core import (
    AgentFinalResult,
    AgentRun,
    AgentRunStatus,
)
from app.application.poster_agent import (
    PosterAgentDraftBuildRequest,
    PosterAgentDraftBuilder,
    PosterAgentDraftStatus,
    PosterAgentPublishDecision,
    PosterAgentVerificationParser,
    PosterPublishDecisionEngine,
)


VERIFICATION_JSON = """
{
  "title": "КИШЛАК",
  "event_type": "concert",
  "artists": ["КИШЛАК"],
  "organizers": [],
  "age_limit": 16,
  "description": "Концерт КИШЛАК в Санкт-Петербурге.",
  "occurrences": [
    {
      "city_name": "Санкт-Петербург",
      "venue_name": "Sound",
      "address": null,
      "event_date": "2026-05-12",
      "start_time": null,
      "doors_time": null,
      "confidence": 0.82,
      "verified": false,
      "source_url": "https://example.com",
      "explanation": "Данные взяты из тестового structured verification."
    }
  ],
  "links": [
    {
      "url": "https://example.com",
      "kind": "ticket",
      "title": "Тестовая билетная ссылка",
      "verified": false,
      "confidence": 0.4,
      "source_type": "url_read",
      "explanation": "Тестовая ссылка."
    }
  ],
  "facts": [],
  "missing_fields": ["verified_ticket_link"],
  "conflicts": [],
  "warnings": ["Тестовые данные не являются реальным подтверждением."],
  "overall_confidence": 0.72,
  "recommendation": "needs_review",
  "explanation": "Черновик требует ручной проверки."
}
"""


def main() -> None:
    parser = PosterAgentVerificationParser()
    verification_result = parser.parse(VERIFICATION_JSON)

    agent_run = AgentRun(
        session_id="test-session",
        request_id="test-request",
        status=AgentRunStatus.FINISHED,
        goal="test poster verification draft builder",
    )

    agent_run.final_result = AgentFinalResult(
        text=VERIFICATION_JSON,
        structured_data={
            "poster_verification": verification_result.to_dict(),
        },
        metadata={
            "test": True,
        },
    )

    builder = PosterAgentDraftBuilder()
    draft = builder.build(
        PosterAgentDraftBuildRequest(
            agent_run=agent_run,
        )
    )

    base_decision = PosterAgentPublishDecision(
        can_publish=True,
        status=PosterAgentDraftStatus.READY_TO_PUBLISH,
        reason="Base validation passed.",
        issues=[],
    )

    decision = PosterPublishDecisionEngine().decide(
        draft=draft,
        validation_decision=base_decision,
    )

    assert draft.title == "КИШЛАК"
    assert draft.artists == ["КИШЛАК"]
    assert len(draft.occurrences) == 1
    assert draft.occurrences[0].city == "Санкт-Петербург"
    assert draft.occurrences[0].date == "2026-05-12"
    assert len(draft.links) == 1
    assert decision.can_publish is False
    assert decision.status == PosterAgentDraftStatus.NEEDS_REVIEW

    print("=== VERIFICATION RESULT ===")
    print(
        json.dumps(
            verification_result.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print("\n=== DRAFT ===")
    print(
        json.dumps(
            draft.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print("\n=== DECISION ===")
    print(
        json.dumps(
            decision.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print("\nok")


if __name__ == "__main__":
    main()

