import asyncio

from app.application.contracts import AIProviderLimits, AIRequest
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class FileLimitMockAIProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "file_mock"

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=70,
            max_media_count=0,
            max_media_caption_length=None,
            max_message_count_per_request=None,
            one_active_request_per_session=True,
            send_large_text_as_file=True,
        )


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            FileLimitMockAIProvider(),
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
        session_id="large-file-test-1",
        provider_name="file_mock",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("ERROR:", response.error)
    print("TEXT:", response.text)
    print("RAW MESSAGES:", len(response.raw_messages))


if __name__ == "__main__":
    asyncio.run(main())
    
