import asyncio

from app.application.contracts import AIProviderLimits, AIRequest
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class SlowAIProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "slow_provider"

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            request_timeout_seconds=0.1,
        )

    async def generate(self, request: AIRequest):
        await asyncio.sleep(1)
        return await super().generate(request)


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            SlowAIProvider(),
            MockAIProvider(),
        ]
    )

    request = AIRequest(
        text="Проверка fallback при timeout",
        session_id="timeout-fallback-test-1",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("ERROR:", response.error)
    print("TEXT:", response.text)
    print("FALLBACK ERRORS:", response.metadata.get("fallback_errors"))


if __name__ == "__main__":
    asyncio.run(main())
    
