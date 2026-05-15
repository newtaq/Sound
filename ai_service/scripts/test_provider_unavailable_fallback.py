import asyncio

from app.application.contracts import AIProviderStatus, AIRequest
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class UnavailableAIProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "unavailable"

    @property
    def status(self) -> AIProviderStatus:
        return AIProviderStatus(
            available=False,
            reason="rate limit",
        )


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            UnavailableAIProvider(),
            MockAIProvider(),
        ]
    )

    request = AIRequest(
        text="Проверка fallback при недоступном провайдере",
        session_id="unavailable-fallback-test-1",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("ERROR:", response.error)
    print("TEXT:", response.text)
    print("FALLBACK ERRORS:", response.metadata.get("fallback_errors"))


if __name__ == "__main__":
    asyncio.run(main())
    
