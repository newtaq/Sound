import asyncio

from app.application.contracts import AIRequest
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class ExceptionAIProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "exception_provider"

    async def generate(self, request: AIRequest):
        raise RuntimeError("Provider crashed")


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            ExceptionAIProvider(),
            MockAIProvider(),
        ]
    )

    request = AIRequest(
        text="Проверка fallback при exception",
        session_id="exception-fallback-test-1",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("ERROR:", response.error)
    print("TEXT:", response.text)
    print("FALLBACK ERRORS:", response.metadata.get("fallback_errors"))


if __name__ == "__main__":
    asyncio.run(main())
    
