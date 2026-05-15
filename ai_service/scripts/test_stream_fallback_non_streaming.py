import asyncio

from app.application.contracts import (
    AIProvider,
    AIProviderCapabilities,
    AIProviderLimits,
    AIRequest,
    AIResponse,
    AIResponseStatus,
)
from app.application.provider_router import AIProviderRouter


class NonStreamingProvider(AIProvider):
    @property
    def name(self) -> str:
        return "non_streaming"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(
            can_stream=False,
        )

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits()

    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            status=AIResponseStatus.OK,
            text="Обычный generate-ответ вместо stream",
            provider_name=self.name,
            session_id=request.session_id,
        )


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            NonStreamingProvider(),
        ]
    )

    request = AIRequest(
        text="Проверка stream fallback",
        session_id="stream-fallback-non-streaming-test-1",
        provider_name="non_streaming",
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
    
