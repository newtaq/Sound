import asyncio
import json

from app.application.ai_service import AIService
from app.application.contracts import (
    AIContentInput,
    AIContentRegistry,
    AIProviderCapabilities,
    AIProviderLimits,
    AIRequest,
    AIResponse,
    AIResponseStatus,
)
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class CustomResultProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "custom_result"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities()

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits()

    async def generate(self, request: AIRequest) -> AIResponse:
        text = json.dumps(
            {
                "content_type": "artist_news",
                "is_useful": True,
                "priority": "medium",
                "confidence": 0.82,
                "main_decision": "attach_artist_news",
                "decisions": [
                    {
                        "type": "attach_artist_news",
                        "confidence": 0.82,
                        "data": {
                            "artist": "Кишлак",
                        },
                    }
                ],
                "variants": [],
                "sql_plan": [],
                "warnings": [],
            },
            ensure_ascii=False,
        )

        return AIResponse(
            status=AIResponseStatus.OK,
            text=text,
            provider_name=self.name,
            session_id=request.session_id,
        )


async def main() -> None:
    registry = AIContentRegistry(
        content_types=[
            "event_announcement",
            "tour_announcement",
            "artist_news",
            "trash",
            "unknown",
        ],
        priorities=[
            "critical",
            "high",
            "medium",
            "low",
            "trash",
        ],
        decision_types=[
            "create_event_candidate",
            "create_tour_candidate",
            "attach_artist_news",
            "ignore",
            "needs_review",
        ],
    )

    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                CustomResultProvider(),
            ]
        ),
        content_registry=registry,
    )

    result = await service.analyze_content_result(
        content=AIContentInput(
            text="Кишлак выпустил новый пост про подготовку к туру.",
            source_type="social_post",
            source_platform="vk",
            source_item_id="vk-post-1",
        ),
        provider_name="custom_result",
        session_id="custom-registry-test-1",
    )

    print("RESULT:", result)
    if result is not None:
        print("RAW CONTENT TYPE:", result.raw["content_type"])
        print("RAW DECISION:", result.raw["main_decision"])
        print("DECISIONS:", result.decisions)


if __name__ == "__main__":
    asyncio.run(main())
    
