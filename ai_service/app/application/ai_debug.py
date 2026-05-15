from typing import Protocol

from app.application.contracts import (
    AIRequest,
    AIResponse,
    AIStreamChunk,
)


class AIVisualDebugSink(Protocol):
    def emit_request(
        self,
        request: AIRequest,
        provider_name: str | None = None,
    ) -> None:
        ...

    def emit_response(
        self,
        request: AIRequest,
        response: AIResponse,
    ) -> None:
        ...

    def emit_stream_chunk(
        self,
        request: AIRequest,
        chunk: AIStreamChunk,
    ) -> None:
        ...
