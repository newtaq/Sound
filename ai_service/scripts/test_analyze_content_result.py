import asyncio

from app.application.ai_service import AIService
from app.application.contracts import AIContentInput
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.content_mock import ContentMockAIProvider


async def main() -> None:
    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                ContentMockAIProvider(),
            ]
        )
    )

    content = AIContentInput(
        text="Кишлак. Тур 2026. 12 мая — Москва, 14 мая — Санкт-Петербург. Билеты скоро.",
        source_type="telegram_post",
        source_id="test_channel",
        source_post_id="123",
        published_at="2026-05-02T00:00:00+03:00",
    )

    result = await service.analyze_content_result(
        content=content,
        provider_name="content_mock",
        session_id="content-result-test-1",
    )

    print("RESULT:", result)
    if result is not None:
        print("CONTENT TYPE:", result.content_type)
        print("DECISION:", result.main_decision)
        print("CONFIDENCE:", result.confidence)


if __name__ == "__main__":
    asyncio.run(main())
    
