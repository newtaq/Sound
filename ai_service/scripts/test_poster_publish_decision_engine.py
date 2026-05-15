from app.application.poster_agent import (
    PosterAgentDraft,
    PosterAgentDraftStatus,
    PosterAgentLink,
    PosterAgentLinkType,
    PosterAgentOccurrence,
    PosterAgentPublishDecision,
    PosterPublishDecisionEngine,
)


def build_validation_decision() -> PosterAgentPublishDecision:
    return PosterAgentPublishDecision(
        can_publish=True,
        status=PosterAgentDraftStatus.READY_TO_PUBLISH,
        reason="Base validation passed.",
        issues=[],
    )


def test_auto_publish() -> None:
    draft = PosterAgentDraft(
        title="КИШЛАК",
        event_type="concert",
        artists=["КИШЛАК"],
        age_limit=16,
        description="Концерт в Санкт-Петербурге.",
        occurrences=[
            PosterAgentOccurrence(
                city="Санкт-Петербург",
                venue="Sound",
                date="2026-05-12",
                confidence="high",
                verified=True,
            )
        ],
        links=[
            PosterAgentLink(
                url="https://example.com",
                link_type=PosterAgentLinkType.TICKET,
                verified=True,
                metadata={
                    "confidence": 0.95,
                },
            )
        ],
        source_text="",
        metadata={
            "overall_confidence": 0.92,
            "recommendation": "auto_publish",
            "missing_fields": [],
            "conflicts": [],
        },
    )

    decision = PosterPublishDecisionEngine().decide(
        draft=draft,
        validation_decision=build_validation_decision(),
    )

    assert decision.can_publish is True
    assert decision.status == PosterAgentDraftStatus.READY_TO_PUBLISH
    assert decision.metadata["publish_status"] == "auto_publish"


def test_needs_review_without_verified_link() -> None:
    draft = PosterAgentDraft(
        title="КИШЛАК",
        event_type="concert",
        artists=["КИШЛАК"],
        age_limit=16,
        description="Концерт в Санкт-Петербурге.",
        occurrences=[
            PosterAgentOccurrence(
                city="Санкт-Петербург",
                venue="Sound",
                date="2026-05-12",
                confidence="high",
                verified=True,
            )
        ],
        links=[
            PosterAgentLink(
                url="https://example.com",
                link_type=PosterAgentLinkType.TICKET,
                verified=False,
                metadata={
                    "confidence": 0.4,
                },
            )
        ],
        source_text="",
        metadata={
            "overall_confidence": 0.88,
            "recommendation": "needs_review",
            "missing_fields": ["verified_ticket_link"],
            "conflicts": [],
        },
    )

    decision = PosterPublishDecisionEngine().decide(
        draft=draft,
        validation_decision=build_validation_decision(),
    )

    assert decision.can_publish is False
    assert decision.status == PosterAgentDraftStatus.NEEDS_REVIEW
    assert decision.metadata["publish_status"] == "needs_review"


def test_blocked_without_occurrence() -> None:
    draft = PosterAgentDraft(
        title="КИШЛАК",
        event_type="concert",
        artists=["КИШЛАК"],
        age_limit=16,
        description="Концерт.",
        occurrences=[],
        links=[],
        source_text="",
        metadata={
            "overall_confidence": 0.2,
            "recommendation": "blocked",
            "missing_fields": ["date", "city"],
            "conflicts": [],
        },
    )

    decision = PosterPublishDecisionEngine().decide(
        draft=draft,
        validation_decision=build_validation_decision(),
    )

    assert decision.can_publish is False
    assert decision.status == PosterAgentDraftStatus.BLOCKED
    assert decision.metadata["publish_status"] == "blocked"


def main() -> None:
    test_auto_publish()
    test_needs_review_without_verified_link()
    test_blocked_without_occurrence()

    print("ok")


if __name__ == "__main__":
    main()


