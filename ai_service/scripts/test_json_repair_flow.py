import asyncio
import json

from app.application.ai_service import AIService
from app.application.contracts import (
    AIContentInput,
    AIProviderCapabilities,
    AIProviderLimits,
    AIRequest,
    AIResponse,
    AIResponseStatus,
)
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class BrokenThenRepairProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "broken_then_repair"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities()

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits()

    async def generate(self, request: AIRequest) -> AIResponse:
        if request.metadata.get("task") == "repair_json_response":
            text = json.dumps(
                {
                    "content_type": "tour_announcement",
                    "is_useful": True,
                    "priority": "high",
                    "confidence": 0.88,
                    "main_decision": "create_tour_candidate",
                    "decisions": [
                        {
                            "type": "create_tour_candidate",
                            "confidence": 0.88,
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
        else:
            text = "content_type: tour_announcement, confidence: 0.88"

        return AIResponse(
            status=AIResponseStatus.OK,
            text=text,
            provider_name=self.name,
            session_id=request.session_id,
        )


async def main() -> None:
    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                BrokenThenRepairProvider(),
            ]
        )
    )

    result = await service.analyze_content_result(
        content=AIContentInput(
            text="Кишлак. Тур 2026. Москва и Санкт-Петербург. Билеты скоро.",
            source_type="social_post",
            source_platform="telegram",
            source_item_id="repair-test-post-1",
        ),
        provider_name="broken_then_repair",
        session_id="json-repair-flow-test-1",
    )

    print("RESULT:", result)
    if result is not None:
        print("CONTENT TYPE:", result.content_type)
        print("DECISION:", result.main_decision)
        print("WARNINGS:", result.warnings)


if __name__ == "__main__":
    asyncio.run(main())
    
