import asyncio

from app.application.contracts import AIProviderLimits, AIRequest
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class SmallLimitMockAIProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "small_mock"

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=70,
            max_media_count=0,
            max_media_caption_length=None,
            max_message_count_per_request=None,
            one_active_request_per_session=True,
        )


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            SmallLimitMockAIProvider(),
        ]
    )

    request = AIRequest(
        text=(
            "Кишлак. Тур 2026. "
            "12 мая — Москва. "
            "14 мая — Санкт-Петербург. "
            "16 мая — Казань. "
            "18 мая — Екатеринбург. "
            "Билеты скоро."
        ),
        session_id="multipart-test-1",
        provider_name="small_mock",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("ERROR:", response.error)
    print("MULTIPART:", response.metadata.get("is_multipart"))
    print("PART TOTAL:", response.metadata.get("part_total"))
    print("RAW MESSAGES:", len(response.raw_messages))

    for index, message in enumerate(response.raw_messages, start=1):
        print("=" * 30)
        print("RAW", index)
        print(message)


if __name__ == "__main__":
    asyncio.run(main())
    
