import asyncio
import json

from app.application.contracts import AIMode, AIStreamEventType
from scripts.test_groq_vision import ensure_test_image
from app.application.contracts import AIMedia, AIMediaType
from app.infrastructure.service_factory import build_ai_client


async def main() -> None:
    image_path = ensure_test_image()

    client = build_ai_client(
        provider_names=[
            "groq_vision",
        ]
    )

    event_counts = {}
    full_text = ""
    native_stream_seen = False

    async for chunk in client.stream(
        text=(
            "Посмотри на изображение. Ответь коротко: "
            "какие основные цвета на нём видны?"
        ),
        provider_name="groq_vision",
        mode=AIMode.FAST,
        session_id="groq-vision-native-stream-smoke-test",
        media=[
            AIMedia(
                media_type=AIMediaType.IMAGE,
                path=str(image_path),
                mime_type="image/png",
                filename="groq_vision_test.png",
            )
        ],
        use_history=False,
        metadata={
            "script": "test_groq_vision_stream",
        },
    ):
        event_counts[chunk.event_type.value] = event_counts.get(chunk.event_type.value, 0) + 1

        if chunk.metadata.get("stream_transport") == "groq_vision_native_stream":
            native_stream_seen = True

        if chunk.event_type == AIStreamEventType.MESSAGE_UPDATED:
            print("DELTA:", chunk.text)
            full_text = chunk.full_text

        if chunk.event_type == AIStreamEventType.ERROR:
            print("ERROR:", chunk.error)
            print(
                json.dumps(
                    chunk.metadata,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            raise RuntimeError(chunk.error)

        if chunk.event_type == AIStreamEventType.FINISHED:
            full_text = chunk.full_text
            print()
            print("FINISHED")
            print("FULL:", full_text)
            print("METADATA:")
            print(
                json.dumps(
                    chunk.metadata,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

    assert native_stream_seen is True
    assert event_counts.get("started", 0) == 1
    assert event_counts.get("message_updated", 0) >= 1
    assert event_counts.get("finished", 0) == 1
    assert full_text.strip()

    print()
    print("EVENT_COUNTS:", event_counts)
    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
