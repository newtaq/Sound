import asyncio

from app.application.ai_service import AIService
from app.application.contracts import AIRequest
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            MockAIProvider(),
        ]
    )
    service = AIService(provider_router=router)

    request = AIRequest(
        text="Проверка AI service",
        session_id="test-session-1",
        provider_name="mock",
    )

    response = await service.generate(request)
    print("GENERATE:")
    print(response.text)

    print()
    print("STREAM:")
    async for chunk in service.stream(request):
        print(chunk.event_type, chunk.text, chunk.full_text)


if __name__ == "__main__":
    asyncio.run(main())
    
