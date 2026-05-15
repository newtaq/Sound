from app.application.contracts import (
    AIMode,
    AIRequest,
    AIStreamChunk,
    AIStreamEventType,
)
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
    request = AIRequest(
        text="stream test",
        session_id="stream-debug-session",
        mode=AIMode.FAST,
        provider_name="groq",
        metadata={
            "event_title": "КИШЛАК",
            "event_date": "2026-05-12",
        },
    )

    started = AIStreamChunk(
        event_type=AIStreamEventType.STARTED,
        provider_name="groq",
        session_id=request.session_id,
        request_id=request.request_id,
    )
    delta = AIStreamChunk(
        event_type=AIStreamEventType.MESSAGE_UPDATED,
        text="часть",
        full_text="часть",
        provider_name="groq",
        session_id=request.session_id,
        request_id=request.request_id,
    )
    finished = AIStreamChunk(
        event_type=AIStreamEventType.FINISHED,
        full_text="часть ответа целиком",
        provider_name="groq",
        session_id=request.session_id,
        request_id=request.request_id,
    )

    recorder = RecordingTelegramSink()
    quiet_sink = TelegramAIVisualDebugSink(
        config=TelegramVisualDebugConfig(
            enabled=True,
            include_stream_deltas=False,
        ),
        telegram_sink=recorder,
    )

    quiet_sink.emit_stream_chunk(request, started)
    quiet_sink.emit_stream_chunk(request, delta)
    quiet_sink.emit_stream_chunk(request, finished)

    assert [message.kind.value for message in recorder.messages] == [
        "stream_started",
        "stream_finished",
    ]

    recorder = RecordingTelegramSink()
    verbose_sink = TelegramAIVisualDebugSink(
        config=TelegramVisualDebugConfig(
            enabled=True,
            include_stream_deltas=True,
        ),
        telegram_sink=recorder,
    )

    verbose_sink.emit_stream_chunk(request, started)
    verbose_sink.emit_stream_chunk(request, delta)
    verbose_sink.emit_stream_chunk(request, finished)

    assert [message.kind.value for message in recorder.messages] == [
        "stream_started",
        "stream_delta",
        "stream_finished",
    ]

    assert recorder.messages[1].text == "часть"

    print("ok")


if __name__ == "__main__":
    main()
