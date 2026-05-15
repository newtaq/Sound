import asyncio

from app.application.contracts import AIProviderLimits, AIRequest, AIResponse, AIResponseStatus
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class RetrySuccessProvider(MockAIProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "retry_success"

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            retry_count=1,
            retry_delay_seconds=0,
        )

    async def generate(self, request: AIRequest) -> AIResponse:
        self.calls += 1

        if self.calls == 1:
            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=self.name,
                session_id=request.session_id,
                error="Temporary failure",
            )

        return await super().generate(request)


async def main() -> None:
    provider = RetrySuccessProvider()

    router = AIProviderRouter(
        providers=[
            provider,
            MockAIProvider(),
        ]
    )

    request = AIRequest(
        text="Проверка retry",
        session_id="retry-success-test-1",
        provider_name="retry_success",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("ERROR:", response.error)
    print("CALLS:", provider.calls)
    print("RETRY ATTEMPTS:", response.metadata.get("retry_attempts"))
    print("FALLBACK ERRORS:", response.metadata.get("fallback_errors"))
    print("TEXT:", response.text)


if __name__ == "__main__":
    asyncio.run(main())
    
