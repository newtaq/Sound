from app.application.contracts import AIResponse, AIResponseStatus
from app.application.parsing import AnalysisResponseParser


def main() -> None:
    parser = AnalysisResponseParser()

    response = AIResponse(
        status=AIResponseStatus.OK,
        text=(
            "Вот результат анализа:\n"
            "{"
            '"content_type":"tour_announcement",'
            '"is_useful":true,'
            '"priority":"high",'
            '"confidence":0.91,'
            '"main_decision":"create_tour_candidate",'
            '"decisions":[{"type":"create_tour_candidate","confidence":0.91,"data":{}}],'
            '"variants":[],'
            '"sql_plan":[],'
            '"warnings":[]'
            "}\n"
            "Готово."
        ),
        provider_name="test",
        session_id="json-extraction-test-1",
    )

    parsed = parser.parse(response)
    result = parser.parse_result(response)

    print("PARSED OK:", parsed.ok)
    print("PARSED WARNINGS:", parsed.warnings)
    print("RESULT:", result)

    if result is not None:
        print("CONTENT TYPE:", result.content_type)
        print("DECISION:", result.main_decision)
        print("WARNINGS:", result.warnings)


if __name__ == "__main__":
    main()
    
