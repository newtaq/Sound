import asyncio

from app.application.ai_service import AIService
from app.application.contracts import AIContentInput
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


async def main() -> None:
    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                MockAIProvider(),
            ]
        )
    )

    content = AIContentInput(
        text="Кишлак. Тур 2026. 12 мая — Москва, 14 мая — Санкт-Петербург. Билеты скоро.",
        source_type="telegram_post",
        source_id="test_channel",
        source_post_id="123",
        published_at="2026-05-02T00:00:00+03:00",
        links=[],
        preprocessing={
            "ocr_text": None,
            "parsed_links": [],
            "preliminary_draft": {},
            "db_matches": [],
        },
    )

    response = await service.analyze_content(
        content=content,
        provider_name="mock",
        session_id="content-test-1",
    )

    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
    
