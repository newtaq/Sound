import asyncio
from typing import Any

from app.application.ai_service import AIService
from app.application.contracts import AIContentInput, AIRequest, AIResponse
from app.application.db import AIDatabaseGateway
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.content_mock import ContentMockAIProvider


class CountingContentMockAIProvider(ContentMockAIProvider):
    def __init__(self) -> None:
        self.generate_calls = 0

    async def generate(self, request: AIRequest) -> AIResponse:
        self.generate_calls += 1
        return await super().generate(request)


class RecordingDatabaseGateway(AIDatabaseGateway):
    def __init__(self) -> None:
        self.saved_results: list[dict[str, Any]] = []

    async def search_context(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return []

    async def save_analysis_result(self, result: dict[str, Any]) -> None:
        self.saved_results.append(result)


async def main() -> None:
    provider = CountingContentMockAIProvider()
    database = RecordingDatabaseGateway()

    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                provider,
            ]
        ),
        database_gateway=database,
    )

    content = AIContentInput(
        text="Кишлак. Тур 2026. 12 мая — Москва. 14 мая — Санкт-Петербург.",
        source_type="social_post",
        source_platform="telegram",
        source_item_id="cache-hit-test-post-1",
    )

    first_result = await service.analyze_content_result(
        content=content,
        provider_name="content_mock",
        session_id="cache-hit-test-1",
    )

    second_result = await service.analyze_content_result(
        content=content,
        provider_name="content_mock",
        session_id="cache-hit-test-2",
    )

    print("FIRST RESULT:", first_result)
    print("SECOND RESULT:", second_result)
    print("PROVIDER CALLS:", provider.generate_calls)
    print("DB SAVED COUNT:", len(database.saved_results))

    if second_result is not None:
        print("SECOND WARNINGS:", second_result.warnings)

    if provider.generate_calls != 1:
        raise SystemExit(f"Expected 1 provider call, got {provider.generate_calls}")

    if len(database.saved_results) != 1:
        raise SystemExit(f"Expected 1 saved result, got {len(database.saved_results)}")

    if second_result is None:
        raise SystemExit("Second result is None")

    if "Loaded analysis result from cache" not in second_result.warnings:
        raise SystemExit("Second result was not loaded from cache")


if __name__ == "__main__":
    asyncio.run(main())
    
