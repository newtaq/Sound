import asyncio
from collections.abc import AsyncIterator

from app.application.contracts import (
    AIProviderCapabilities,
    AIProviderLimits,
    AIRequest,
    AIResponse,
    AIResponseStatus,
    AIStreamChunk,
    StreamingAIProvider,
)
from app.application.provider_router import AIProviderRouter


class BrokenStreamProvider(StreamingAIProvider):
    @property
    def name(self) -> str:
        return "broken_stream"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(
            can_stream=True,
        )

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits()

    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            status=AIResponseStatus.OK,
            text="Ответ через generate после падения stream",
            provider_name=self.name,
            session_id=request.session_id,
        )

    def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        return self._stream(request)

    async def _stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        raise RuntimeError("Stream crashed")
        yield


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            BrokenStreamProvider(),
        ]
    )

    request = AIRequest(
        text="Проверка stream exception fallback",
        session_id="stream-fallback-exception-test-1",
        provider_name="broken_stream",
    )

    async for chunk in router.stream(request):
        print("EVENT:", chunk.event_type)
        print("TEXT:", chunk.text)
        print("FULL TEXT:", chunk.full_text)
        print("PROVIDER:", chunk.provider_name)
        print("METADATA:", chunk.metadata)
        print("ERROR:", chunk.error)


if __name__ == "__main__":
    asyncio.run(main())
    
