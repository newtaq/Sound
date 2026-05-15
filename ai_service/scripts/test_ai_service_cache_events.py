import asyncio
from typing import Any

from app.application.ai_service import AIService
from app.application.contracts import AIContentInput, AIRequest, AIResponse
from app.application.db import AIDatabaseGateway
from app.application.observability import MemoryAIEventLogger
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
    event_logger = MemoryAIEventLogger()

    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                provider,
            ]
        ),
        database_gateway=database,
        event_logger=event_logger,
    )

    content = AIContentInput(
        text="Кишлак. Тур 2026. 12 мая — Москва. 14 мая — Санкт-Петербург.",
        source_type="social_post",
        source_platform="telegram",
        source_item_id="cache-events-test-post-1",
    )

    first_result = await service.analyze_content_result(
        content=content,
        provider_name="content_mock",
        session_id="cache-events-test-1",
    )

    second_result = await service.analyze_content_result(
        content=content,
        provider_name="content_mock",
        session_id="cache-events-test-2",
    )

    event_names = [event.name for event in event_logger.events]

    print("FIRST RESULT:", first_result)
    print("SECOND RESULT:", second_result)
    print("PROVIDER CALLS:", provider.generate_calls)
    print("DB SAVED COUNT:", len(database.saved_results))
    print("EVENTS COUNT:", len(event_logger.events))
    print("EVENT NAMES:", event_names)

    for event in event_logger.events:
        print(
            "EVENT:",
            event.name,
            event.level,
            event.session_id,
            event.provider_name,
            event.metadata.get("source_item_id"),
        )

    if provider.generate_calls != 1:
        raise SystemExit(f"Expected 1 provider call, got {provider.generate_calls}")

    if len(database.saved_results) != 1:
        raise SystemExit(f"Expected 1 saved result, got {len(database.saved_results)}")

    if second_result is None:
        raise SystemExit("Second result is None")

    if "analysis_cache_miss" not in event_names:
        raise SystemExit("Cache miss event was not logged")

    if "analysis_cache_hit" not in event_names:
        raise SystemExit("Cache hit event was not logged")


if __name__ == "__main__":
    asyncio.run(main())
    
