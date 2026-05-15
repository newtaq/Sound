from app.application.contracts import AIRequest
from app.infrastructure.telegram_debug import (
    TelegramAIVisualDebugSink,
    TelegramDebugMessage,
    TelegramVisualDebugConfig,
)


class RecordingTelegramSink:
    def __init__(self) -> None:
        self.messages: list[TelegramDebugMessage] = []

    def emit_background(
        self,
        message: TelegramDebugMessage,
    ) -> None:
        self.messages.append(message)


def main() -> None:
    recorder = RecordingTelegramSink()
    sink = TelegramAIVisualDebugSink(
        config=TelegramVisualDebugConfig(
            enabled=True,
        ),
        telegram_sink=recorder,
    )

    request = AIRequest(
        text=(
            "Из этих данных собери черновик афиши:\n\n"
            "КИШЛАК\n\n"
            "12 мая  Санкт-Петербург\n"
            "Клуб Sound\n\n"
            "Билеты: https://example.com"
        ),
        session_id="event-title-extract-test",
        provider_name="groq",
        metadata={},
    )

    sink.emit_request(request)

    assert len(recorder.messages) == 1

    message = recorder.messages[0]

    assert message.event_title == "КИШЛАК"
    assert message.metadata["event_title"] == "КИШЛАК"
    assert message.metadata["event_date"] == "12 мая"

    recorder = RecordingTelegramSink()
    sink = TelegramAIVisualDebugSink(
        config=TelegramVisualDebugConfig(
            enabled=True,
        ),
        telegram_sink=recorder,
    )

    request = AIRequest(
        text="Ответь одной строкой.",
        session_id="metadata-priority-test",
        provider_name="groq",
        metadata={
            "event_title": "Название из metadata",
            "event_date": "2026-05-12",
        },
    )

    sink.emit_request(request)

    message = recorder.messages[0]

    assert message.event_title == "Название из metadata"
    assert message.metadata["event_title"] == "Название из metadata"
    assert message.metadata["event_date"] == "2026-05-12"

    print("ok")


if __name__ == "__main__":
    main()
