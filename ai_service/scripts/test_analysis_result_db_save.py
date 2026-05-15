import asyncio
from typing import Any

from app.application.ai_service import AIService
from app.application.contracts import AIContentInput
from app.application.db import AIDatabaseGateway
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.content_mock import ContentMockAIProvider


class RecordingDatabaseGateway(AIDatabaseGateway):
    def __init__(self) -> None:
        self.saved_results: list[dict[str, Any]] = []

    async def search_context(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return []

    async def save_analysis_result(self, result: dict[str, Any]) -> None:
        self.saved_results.append(result)


async def main() -> None:
    database = RecordingDatabaseGateway()

    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                ContentMockAIProvider(),
            ]
        ),
        database_gateway=database,
    )

    result = await service.analyze_content_result(
        content=AIContentInput(
            text="Кишлак. Тур 2026. 12 мая — Москва. 14 мая — Санкт-Петербург.",
            source_type="social_post",
            source_platform="telegram",
            source_item_id="db-save-test-post-1",
        ),
        provider_name="content_mock",
        session_id="db-save-test-1",
    )

    print("RESULT:", result)
    print("SAVED COUNT:", len(database.saved_results))

    if database.saved_results:
        saved = database.saved_results[0]

        print("SAVED CONTENT TYPE:", saved["content_type"])
        print("SAVED DECISION:", saved["main_decision"])
        print("SAVED DECISIONS COUNT:", len(saved["decisions"]))
        print("SAVED EVIDENCE COUNT:", len(saved["decisions"][0]["evidence"]))


if __name__ == "__main__":
    asyncio.run(main())
    
