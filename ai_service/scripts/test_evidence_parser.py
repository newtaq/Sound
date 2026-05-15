from app.application.contracts import AIResponse, AIResponseStatus
from app.application.parsing import AnalysisResponseParser


def main() -> None:
    parser = AnalysisResponseParser()

    response = AIResponse(
        status=AIResponseStatus.OK,
        text=(
            "{"
            '"content_type":"tour_announcement",'
            '"is_useful":true,'
            '"priority":"high",'
            '"confidence":0.9,'
            '"main_decision":"create_tour_candidate",'
            '"decisions":[{'
            '"type":"create_tour_candidate",'
            '"confidence":0.9,'
            '"data":{"artist":"Кишлак"},'
            '"evidence":[{'
            '"field":"artist",'
            '"value":"Кишлак",'
            '"source":"text",'
            '"source_text":"Кишлак. Тур 2026.",'
            '"confidence":0.9,'
            '"metadata":{}'
            "}]"
            "}],"
            '"variants":[],'
            '"sql_plan":[],'
            '"warnings":[]'
            "}"
        ),
        provider_name="test",
        session_id="evidence-parser-test-1",
    )

    result = parser.parse_result(response)

    print("RESULT:", result)

    if result is not None:
        decision = result.decisions[0]
        print("DECISION:", decision.type)
        print("EVIDENCE COUNT:", len(decision.evidence))

        if decision.evidence:
            evidence = decision.evidence[0]
            print("EVIDENCE FIELD:", evidence.field)
            print("EVIDENCE VALUE:", evidence.value)
            print("EVIDENCE SOURCE TEXT:", evidence.source_text)


if __name__ == "__main__":
    main()
    
