import asyncio

from app.application.contracts import (
    AIProviderCapabilities,
    AIProviderLimits,
    AIProviderRoutingConfig,
    AIRequest,
    AIResponse,
    AIResponseStatus,
)
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class FailingAIProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "failing"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities()

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits()

    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            status=AIResponseStatus.ERROR,
            text="",
            provider_name=self.name,
            session_id=request.session_id,
            error="Test provider failure",
        )


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            FailingAIProvider(),
            MockAIProvider(),
        ],
        routing_config=AIProviderRoutingConfig(
            enable_fallback=False,
        ),
    )

    request = AIRequest(
        text="Проверка отключенного fallback",
        session_id="fallback-disabled-test-1",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("ERROR:", response.error)
    print("TEXT:", response.text)
    print("FALLBACK ERRORS:", response.metadata.get("fallback_errors"))


if __name__ == "__main__":
    asyncio.run(main())
    
