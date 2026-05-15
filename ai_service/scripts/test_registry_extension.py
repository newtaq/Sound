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


class CustomRegistryProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "custom_registry_provider"

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
                "confidence": 0.77,
                "main_decision": "attach_artist_news",
                "decisions": [
                    {
                        "type": "attach_artist_news",
                        "confidence": 0.77,
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
    registry = AIContentRegistry()
    registry.add_content_type("artist_news")
    registry.add_decision_type("attach_artist_news")

    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                CustomRegistryProvider(),
            ]
        ),
        content_registry=registry,
    )

    result = await service.analyze_content_result(
        content=AIContentInput(
            text="Кишлак выложил новость о подготовке к туру.",
            source_type="social_post",
            source_platform="vk",
            source_item_id="vk-post-2",
        ),
        provider_name="custom_registry_provider",
        session_id="registry-extension-test-1",
    )

    print("RESULT:", result)
    if result is not None:
        print("CONTENT TYPE:", result.content_type)
        print("DECISION:", result.main_decision)


if __name__ == "__main__":
    asyncio.run(main())
    
