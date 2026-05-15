import asyncio
import json

from app.application.contracts import (
    AIMedia,
    AIMediaType,
    AIProviderLimits,
    AIRequest,
    AIResponse,
    AIResponseStatus,
)
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


class MediaLimitMockProvider(MockAIProvider):
    @property
    def name(self) -> str:
        return "media_limit_mock"

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=None,
            max_media_count=2,
            max_media_caption_length=None,
            max_message_count_per_request=None,
            one_active_request_per_session=True,
            send_large_text_as_file=False,
        )

    async def generate(self, request: AIRequest) -> AIResponse:
        text = json.dumps(
            {
                "provider": self.name,
                "text": request.text,
                "media_count": len(request.media),
                "metadata": request.metadata,
            },
            ensure_ascii=False,
        )

        return AIResponse(
            status=AIResponseStatus.OK,
            text=text,
            provider_name=self.name,
            session_id=request.session_id,
            raw_messages=[text],
        )


async def main() -> None:
    router = AIProviderRouter(
        providers=[
            MediaLimitMockProvider(),
        ]
    )

    request = AIRequest(
        text="Проверка media multipart",
        session_id="media-multipart-test-1",
        provider_name="media_limit_mock",
        media=[
            AIMedia(media_type=AIMediaType.IMAGE, media_id="image-1"),
            AIMedia(media_type=AIMediaType.IMAGE, media_id="image-2"),
            AIMedia(media_type=AIMediaType.IMAGE, media_id="image-3"),
            AIMedia(media_type=AIMediaType.IMAGE, media_id="image-4"),
            AIMedia(media_type=AIMediaType.IMAGE, media_id="image-5"),
        ],
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("ERROR:", response.error)
    print("MULTIPART:", response.metadata.get("is_multipart"))
    print("PART TOTAL:", response.metadata.get("part_total"))
    print("RAW MESSAGES:", len(response.raw_messages))

    for index, raw_message in enumerate(response.raw_messages, start=1):
        print("=" * 30)
        print(f"RAW {index}")
        print(raw_message)


if __name__ == "__main__":
    asyncio.run(main())
    
