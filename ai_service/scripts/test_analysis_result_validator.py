from app.application.contracts import AIAnalysisResult, AIDecision
from app.application.validation import AIAnalysisResultValidator


def main() -> None:
    validator = AIAnalysisResultValidator()

    valid_result = AIAnalysisResult(
        content_type="tour_announcement",
        is_useful=True,
        priority="high",
        confidence=0.9,
        main_decision="create_tour_candidate",
        decisions=[
            AIDecision(
                type="create_tour_candidate",
                confidence=0.9,
                data={},
            )
        ],
    )

    trash_with_problem = AIAnalysisResult(
        content_type="trash",
        is_useful=True,
        priority="trash",
        confidence=0.5,
        main_decision="create_event_candidate",
        decisions=[
            AIDecision(
                type="create_event_candidate",
                confidence=0.5,
                data={},
            )
        ],
    )

    print("VALID:", validator.validate(valid_result))
    print("TRASH PROBLEM:", validator.validate(trash_with_problem))


if __name__ == "__main__":
    main()
    
