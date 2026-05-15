import json

from app.application.contracts import (
    AIAnalysisResult,
    AIDecision,
    AIEvidence,
)
from app.application.serialization import AIAnalysisResultSerializer


def main() -> None:
    serializer = AIAnalysisResultSerializer()

    result = AIAnalysisResult(
        content_type="tour_announcement",
        is_useful=True,
        priority="high",
        confidence=0.9,
        main_decision="create_tour_candidate",
        decisions=[
            AIDecision(
                type="create_tour_candidate",
                confidence=0.9,
                data={
                    "tour_title": "Кишлак. Тур 2026",
                    "artists": ["Кишлак"],
                },
                evidence=[
                    AIEvidence(
                        field="artist",
                        value="Кишлак",
                        source="text",
                        source_text="Кишлак. Тур 2026.",
                        confidence=0.9,
                    )
                ],
            )
        ],
        warnings=[],
    )

    data = serializer.to_dict(result)
    restored = serializer.from_dict(data)

    print("DICT:", data)
    print("JSON:", json.dumps(data, ensure_ascii=False))

    print("CONTENT TYPE:", data["content_type"])
    print("DECISION:", data["decisions"][0]["type"])
    print("EVIDENCE FIELD:", data["decisions"][0]["evidence"][0]["field"])

    print("RESTORED:", restored)

    if restored is not None:
        print("RESTORED CONTENT TYPE:", restored.content_type)
        print("RESTORED DECISION:", restored.decisions[0].type)
        print("RESTORED EVIDENCE FIELD:", restored.decisions[0].evidence[0].field)


if __name__ == "__main__":
    main()
    
