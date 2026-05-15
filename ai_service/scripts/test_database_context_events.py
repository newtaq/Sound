import asyncio
from typing import Any

from app.application.ai_service import AIService
from app.application.contracts import AIContentInput, AIRequest, AIResponse
from app.application.db import AIDatabaseGateway
from app.application.observability import MemoryAIEventLogger
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.content_mock import ContentMockAIProvider


class RecordingContentMockAIProvider(ContentMockAIProvider):
    async def generate(self, request: AIRequest) -> AIResponse:
        return await super().generate(request)


class ContextDatabaseGateway(AIDatabaseGateway):
    async def search_context(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return [
            {
                "entity_type": "artist",
                "name": "Кишлак",
                "confidence": 0.99,
            }
        ]

    async def save_analysis_result(self, result: dict[str, Any]) -> None:
        return None


async def main() -> None:
    event_logger = MemoryAIEventLogger()

    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                RecordingContentMockAIProvider(),
            ]
        ),
        database_gateway=ContextDatabaseGateway(),
        event_logger=event_logger,
    )

    result = await service.analyze_content_result(
        content=AIContentInput(
            text="Кишлак. Тур 2026. 12 мая — Москва.",
            source_type="social_post",
            source_platform="telegram",
            source_item_id="db-context-events-test-1",
        ),
        provider_name="content_mock",
        session_id="db-context-events-session-1",
    )

    event_names = [event.name for event in event_logger.events]

    print("RESULT:", result)
    print("EVENTS COUNT:", len(event_logger.events))
    print("EVENT NAMES:", event_names)

    for event in event_logger.events:
        print(
            "EVENT:",
            event.name,
            event.level,
            event.session_id,
            event.provider_name,
            event.metadata,
        )

    if "analysis_cache_miss" not in event_names:
        raise SystemExit("Cache miss event was not logged")

    if "db_context_loaded" not in event_names:
        raise SystemExit("DB context loaded event was not logged")

    db_events = [
        event
        for event in event_logger.events
        if event.name == "db_context_loaded"
    ]

    if db_events[0].metadata.get("items_count") != 1:
        raise SystemExit("Invalid db context items count")


if __name__ == "__main__":
    asyncio.run(main())
    
