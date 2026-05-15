from app.application.poster_agent.pipeline import (
    PosterAgentPipeline,
    PosterAgentPipelineRequest,
)


def main() -> None:
    pipeline = PosterAgentPipeline(agent_runner=object())

    request = PosterAgentPipelineRequest(
        input_text=(
            "КИШЛАК\n"
            "12.05.2026\n"
            "Санкт-Петербург\n"
            "Билеты: https://example.com\n"
        ),
    )

    metadata = pipeline._build_visual_debug_metadata(request)

    assert metadata["event_title"] == "КИШЛАК"
    assert metadata["event_date"] == "12.05.2026"
    assert metadata["telegram_debug_event_title_source"] == "input_text"
    assert metadata["telegram_debug_event_date_source"] == "input_text"

    request_with_explicit_metadata = PosterAgentPipelineRequest(
        input_text="Любой текст\n13 мая 2026",
        metadata={
            "event_title": "Явное название",
            "event_date": "01.01.2026",
        },
    )

    metadata = pipeline._build_visual_debug_metadata(request_with_explicit_metadata)

    assert metadata["event_title"] == "Явное название"
    assert metadata["event_date"] == "01.01.2026"
    assert metadata["telegram_debug_event_title_source"] == "metadata"
    assert metadata["telegram_debug_event_date_source"] == "metadata"

    request_with_label = PosterAgentPipelineRequest(
        input_text=(
            "Название: Большой концерт\n"
            "Когда: 2026-06-14\n"
        ),
    )

    metadata = pipeline._build_visual_debug_metadata(request_with_label)

    assert metadata["event_title"] == "Большой концерт"
    assert metadata["event_date"] == "14.06.2026"

    print("ok")


if __name__ == "__main__":
    main()
