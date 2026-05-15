from __future__ import annotations

from types import SimpleNamespace

from app.application.poster_agent.url_evidence_verifier import (
    PosterUrlEvidenceVerifier,
)
from app.application.poster_agent.verification_enums import (
    PosterAgentFactStatus,
    PosterAgentSourceType,
)
from app.application.poster_agent.verification_models import (
    PosterAgentVerificationFact,
    PosterAgentVerificationLink,
    PosterAgentVerificationOccurrence,
    PosterAgentVerificationResult,
)


def main() -> None:
    verification_result = PosterAgentVerificationResult(
        title="Pepel Nahudi",
        event_type="concert",
        artists=["Pepel Nahudi"],
        age_limit=16,
        occurrences=[
            PosterAgentVerificationOccurrence(
                city_name="Санкт-Петербург",
                venue_name="Муз Порт",
                event_date="20 августа",
                confidence=0.5,
                verified=False,
            )
        ],
        links=[
            PosterAgentVerificationLink(
                url="https://clck.ru/3THNTP",
                kind="ticket",
                verified=False,
                confidence=0.4,
                source_type=PosterAgentSourceType.UNKNOWN,
            ),
            PosterAgentVerificationLink(
                url="https://red-summer.ru",
                kind="official",
                title="RED SUMMER 2026",
                verified=False,
                confidence=0.4,
                source_type=PosterAgentSourceType.UNKNOWN,
            ),
            PosterAgentVerificationLink(
                url="https://t.me/+pDVpAvK4hBZlNzAy",
                kind="social",
                verified=False,
                confidence=0.4,
                source_type=PosterAgentSourceType.UNKNOWN,
            ),
        ],
        facts=[
            PosterAgentVerificationFact(
                field="artist",
                value="Pepel Nahudi",
                status=PosterAgentFactStatus.UNVERIFIED,
                source_type=PosterAgentSourceType.INPUT_TEXT,
                confidence=0.5,
            ),
            PosterAgentVerificationFact(
                field="date",
                value="20 августа",
                status=PosterAgentFactStatus.UNVERIFIED,
                source_type=PosterAgentSourceType.INPUT_TEXT,
                confidence=0.5,
            ),
            PosterAgentVerificationFact(
                field="city",
                value="Санкт-Петербург",
                status=PosterAgentFactStatus.UNVERIFIED,
                source_type=PosterAgentSourceType.INPUT_TEXT,
                confidence=0.5,
            ),
            PosterAgentVerificationFact(
                field="venue",
                value="Муз Порт",
                status=PosterAgentFactStatus.UNVERIFIED,
                source_type=PosterAgentSourceType.INPUT_TEXT,
                confidence=0.5,
            ),
            PosterAgentVerificationFact(
                field="price",
                value="от 2300 ₽",
                status=PosterAgentFactStatus.UNVERIFIED,
                source_type=PosterAgentSourceType.INPUT_TEXT,
                confidence=0.5,
            ),
        ],
        overall_confidence=0.5,
    )

    tool_outputs = [
        SimpleNamespace(
            tool_name="url_read",
            ok=True,
            data={
                "pages": [
                    {
                        "url": "https://clck.ru/3THNTP",
                        "ok": True,
                        "blocked_by_antibot": False,
                        "status_code": 200,
                        "final_url": "https://ticketscloud.com/v1/widgets/common?event=69e4b01f53d12beff81fa322",
                        "content_type": "text/html",
                        "title": "Ticketscloud",
                        "description": None,
                        "text_preview": "",
                        "error": None,
                    },
                    {
                        "url": "https://red-summer.ru",
                        "ok": True,
                        "blocked_by_antibot": False,
                        "status_code": 200,
                        "final_url": "https://red-summer.ru",
                        "content_type": "text/html; charset=UTF-8",
                        "title": "RED SUMMER 2026",
                        "description": None,
                        "text_preview": (
                            "RED SUMMER 2026 Санкт-Петербург. "
                            "МУЗ ПОРТ — уникальная площадка для летних концертов. "
                            "Какой концерт вас интересует? "
                            "Алёна Швец (23 июля) Pizza (30 июля) "
                            "Pepel Nahudi (20 августа) Loc-Dog (21 августа)."
                        ),
                        "error": None,
                    },
                    {
                        "url": "https://t.me/+pDVpAvK4hBZlNzAy",
                        "ok": True,
                        "blocked_by_antibot": False,
                        "status_code": 200,
                        "final_url": "https://t.me/+pDVpAvK4hBZlNzAy",
                        "content_type": "text/html; charset=utf-8",
                        "title": "Telegram: Join Group Chat",
                        "description": "Главный канал с анонсами",
                        "text_preview": "Фестивали и концерты в Питере",
                        "error": None,
                    },
                ]
            },
        )
    ]

    changed = PosterUrlEvidenceVerifier().apply(
        verification_result=verification_result,
        tool_outputs=tool_outputs,
    )

    assert changed is True

    occurrence = verification_result.occurrences[0]
    assert occurrence.verified is True
    assert occurrence.confidence >= 0.9
    assert occurrence.source_url == "https://red-summer.ru"

    official_link = verification_result.links[1]
    assert official_link.verified is True
    assert official_link.source_type == PosterAgentSourceType.URL
    assert official_link.confidence == 1.0

    ticket_link = verification_result.links[0]
    assert ticket_link.verified is True
    assert ticket_link.source_type == PosterAgentSourceType.URL
    assert ticket_link.confidence >= 0.8

    social_link = verification_result.links[2]
    assert social_link.verified is False

    verified_fields = {
        fact.field
        for fact in verification_result.facts
        if fact.status == PosterAgentFactStatus.VERIFIED
    }

    assert "artist" in verified_fields
    assert "date" in verified_fields
    assert "city" in verified_fields
    assert "venue" in verified_fields
    assert "price" not in verified_fields

    assert verification_result.overall_confidence >= 0.85

    print("ok")


if __name__ == "__main__":
    main()
    