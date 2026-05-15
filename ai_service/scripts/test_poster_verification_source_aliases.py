import json

from app.application.poster_agent import PosterAgentVerificationParser


BASE_JSON = {
    "title": "Test",
    "event_type": "concert",
    "artists": ["Artist"],
    "organizers": [],
    "age_limit": None,
    "description": None,
    "occurrences": [],
    "links": [
        {
            "url": "https://example.com",
            "kind": "ticket",
            "title": "Example",
            "verified": False,
            "confidence": 0.5,
            "source_type": "url_read",
            "explanation": "test",
        }
    ],
    "facts": [
        {
            "field": "ticket_link",
            "value": "https://example.com",
            "status": "unverified",
            "source_type": "groq_search",
            "confidence": 0.5,
            "source_url": "https://example.com",
            "source_title": "Example",
            "explanation": "test",
        }
    ],
    "missing_fields": [],
    "conflicts": [],
    "warnings": [],
    "overall_confidence": 0.5,
    "recommendation": "needs_review",
    "explanation": "test",
}


def main() -> None:
    parser = PosterAgentVerificationParser()
    result = parser.parse(
        json.dumps(
            BASE_JSON,
            ensure_ascii=False,
        )
    )

    assert len(result.links) == 1
    assert len(result.facts) == 1

    assert result.links[0].source_type.value == "url"
    assert result.facts[0].source_type.value == "search"

    print("ok")


if __name__ == "__main__":
    main()
