import asyncio

from app.application.contracts import AIProviderLimits, AIRequest
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class MessageCountLimitProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "message_count_limit"

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=40,
            max_media_count=0,
            max_media_caption_length=None,
            max_message_count_per_request=1,
            one_active_request_per_session=True,
            send_large_text_as_file=False,
        )


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            MessageCountLimitProvider(),
        ]
    )

    request = AIRequest(
        text=(
            "Кишлак. Тур 2026. "
            "12 мая — Москва. "
            "14 мая — Санкт-Петербург. "
            "16 мая — Казань. "
            "18 мая — Екатеринбург."
        ),
        session_id="message-count-limit-test-1",
        provider_name="message_count_limit",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("ERROR:", response.error)
    print("TEXT:", response.text)
    print("FALLBACK ERRORS:", response.metadata.get("fallback_errors"))


if __name__ == "__main__":
    asyncio.run(main())
    
