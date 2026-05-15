import asyncio
from collections.abc import AsyncIterator

from app.application.contracts import (
    AIProviderCapabilities,
    AIProviderLimits,
    AIProviderStatus,
    AIRequest,
    AIResponse,
    AIResponseStatus,
    AIStreamChunk,
    AIStreamEventType,
    StreamingAIProvider,
)
from app.application.provider_router import AIProviderRouter


class RecordingDebugSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, str | None, str | None]] = []

    def emit_request(
        self,
        request: AIRequest,
        provider_name: str | None = None,
    ) -> None:
        self.events.append(
            (
                "request",
                provider_name,
                request.request_id,
            )
        )

    def emit_response(
        self,
        request: AIRequest,
        response: AIResponse,
    ) -> None:
        self.events.append(
            (
                "response",
                response.provider_name,
                response.request_id,
            )
        )

    def emit_stream_chunk(
        self,
        request: AIRequest,
        chunk: AIStreamChunk,
    ) -> None:
        self.events.append(
            (
                f"stream:{chunk.event_type.value}",
                chunk.provider_name,
                chunk.request_id,
            )
        )


class EchoProvider(StreamingAIProvider):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def status(self) -> AIProviderStatus:
        return AIProviderStatus(available=True)

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(can_stream=True)

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=None,
            max_media_count=0,
            max_message_count_per_request=1,
        )

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponse:
        return AIResponse(
            status=AIResponseStatus.OK,
            text=f"echo: {request.text}",
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
            metadata={
                "provider": self.name,
            },
        )

    def stream(
        self,
        request: AIRequest,
    ) -> AsyncIterator[AIStreamChunk]:
        return self._stream(request)

    async def _stream(
        self,
        request: AIRequest,
    ) -> AsyncIterator[AIStreamChunk]:
        yield AIStreamChunk(
            event_type=AIStreamEventType.STARTED,
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
        )

        yield AIStreamChunk(
            event_type=AIStreamEventType.MESSAGE_UPDATED,
            text="echo",
            full_text="echo",
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
        )

        yield AIStreamChunk(
            event_type=AIStreamEventType.FINISHED,
            full_text="echo",
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
        )


async def main() -> None:
    debug_sink = RecordingDebugSink()
    router = AIProviderRouter(
        providers=[EchoProvider()],
        debug_sink=debug_sink,
    )

    request = AIRequest(
        text="hello",
        session_id="debug-session",
        provider_name="echo",
        metadata={
            "event_title": "КИШЛАК",
            "event_date": "2026-05-12",
        },
    )

    response = await router.generate(request)

    assert response.status == AIResponseStatus.OK
    assert debug_sink.events[0][0] == "request"
    assert debug_sink.events[1][0] == "response"
    assert debug_sink.events[0][2] == request.request_id
    assert debug_sink.events[1][2] == request.request_id

    debug_sink.events.clear()

    chunks = [
        chunk
        async for chunk in router.stream(request)
    ]

    assert len(chunks) == 3
    assert debug_sink.events[0][0] == "request"
    assert debug_sink.events[1][0] == "stream:started"
    assert debug_sink.events[2][0] == "stream:message_updated"
    assert debug_sink.events[3][0] == "stream:finished"

    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
