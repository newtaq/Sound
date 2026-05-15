import asyncio
from typing import Any

from app.application.ai_service import AIService
from app.application.contracts import AIContentInput, AIRequest, AIResponse
from app.application.db import AIDatabaseGateway
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.content_mock import ContentMockAIProvider


class RecordingContentMockAIProvider(ContentMockAIProvider):
    def __init__(self) -> None:
        self.last_request_text: str | None = None
        self.generate_calls = 0

    async def generate(self, request: AIRequest) -> AIResponse:
        self.generate_calls += 1
        self.last_request_text = request.text
        return await super().generate(request)


class ContextDatabaseGateway(AIDatabaseGateway):
    def __init__(self) -> None:
        self.search_calls = 0
        self.saved_results: list[dict[str, Any]] = []

    async def search_context(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        self.search_calls += 1

        return [
            {
                "entity_type": "artist",
                "name": "Кишлак",
                "aliases": ["кишлак", "maksim"],
                "confidence": 0.99,
            },
            {
                "entity_type": "venue",
                "name": "VK Stadium",
                "city": "Москва",
                "confidence": 0.87,
            },
        ]

    async def save_analysis_result(self, result: dict[str, Any]) -> None:
        self.saved_results.append(result)


async def main() -> None:
    provider = RecordingContentMockAIProvider()
    database = ContextDatabaseGateway()

    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                provider,
            ]
        ),
        database_gateway=database,
    )

    result = await service.analyze_content_result(
        content=AIContentInput(
            text="Кишлак. Тур 2026. 12 мая — Москва.",
            source_type="social_post",
            source_platform="telegram",
            source_item_id="db-context-prompt-test-1",
        ),
        provider_name="content_mock",
        session_id="db-context-prompt-test-session-1",
    )

    prompt = provider.last_request_text or ""

    print("RESULT:", result)
    print("SEARCH CALLS:", database.search_calls)
    print("PROVIDER CALLS:", provider.generate_calls)
    print("PROMPT HAS ARTIST:", "Кишлак" in prompt)
    print("PROMPT HAS VENUE:", "VK Stadium" in prompt)
    print("PROMPT HAS DB CONTEXT KEY:", "db_context" in prompt)

    if database.search_calls != 1:
        raise SystemExit(f"Expected 1 db context search, got {database.search_calls}")

    if provider.generate_calls != 1:
        raise SystemExit(f"Expected 1 provider call, got {provider.generate_calls}")

    if "VK Stadium" not in prompt:
        raise SystemExit("DB context was not added to prompt")


if __name__ == "__main__":
    asyncio.run(main())
    
