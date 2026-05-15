import json

from app.application.contracts import AIMedia, AIMediaType, AIRequest, AITextFile
from app.infrastructure.providers.mira.config import MiraTelegramProviderConfig
from app.infrastructure.providers.mira.request_payload import (
    MiraTelegramOutgoingMessage,
    MiraTelegramRequestPacker,
)


def main() -> None:
    config = MiraTelegramProviderConfig(
        trigger_prefix="мира",
        max_text_message_length=4096,
        max_caption_length=1024,
        max_media_count=10,
    )

    packer = MiraTelegramRequestPacker(config)

    cases = [
        (
            "short_text",
            AIRequest(
                text="Короткий тестовый запрос.",
                instructions="Ответь коротко.",
                response_format="plain_text",
            ),
        ),
        (
            "long_text",
            AIRequest(
                text="Очень длинный текст.\n" + ("А" * 7000),
                instructions="Проанализируй длинный текст.",
                response_format="plain_text",
            ),
        ),
        (
            "photo_video_short_prompt",
            AIRequest(
                text="Проанализируй эти медиа.",
                instructions="Опиши, что на изображении и видео.",
                media=[
                    AIMedia(
                        media_type=AIMediaType.IMAGE,
                        path="tests/media/poster.jpg",
                        filename="poster.jpg",
                        mime_type="image/jpeg",
                    ),
                    AIMedia(
                        media_type=AIMediaType.VIDEO,
                        path="tests/media/video.mp4",
                        filename="video.mp4",
                        mime_type="video/mp4",
                    ),
                ],
                response_format="plain_text",
            ),
        ),
        (
            "voice_with_caption",
            AIRequest(
                text="Расшифруй голосовое и кратко перескажи.",
                instructions="Сначала расшифровка, потом краткий смысл.",
                media=[
                    AIMedia(
                        media_type=AIMediaType.AUDIO,
                        path="tests/media/voice.ogg",
                        filename="voice.ogg",
                        mime_type="audio/ogg",
                        metadata={"telegram_kind": "voice"},
                    ),
                ],
                response_format="plain_text",
            ),
        ),
        (
            "mixed_media_long_prompt",
            AIRequest(
                text="Длинный запрос с медиа.\n" + ("Б" * 6000),
                instructions="Учти все вложения и полный текст запроса.",
                media=[
                    AIMedia(
                        media_type=AIMediaType.IMAGE,
                        path="tests/media/photo.jpg",
                        filename="photo.jpg",
                        mime_type="image/jpeg",
                    ),
                    AIMedia(
                        media_type=AIMediaType.VIDEO,
                        path="tests/media/video.mp4",
                        filename="video.mp4",
                        mime_type="video/mp4",
                    ),
                    AIMedia(
                        media_type=AIMediaType.DOCUMENT,
                        path="tests/media/file.pdf",
                        filename="file.pdf",
                        mime_type="application/pdf",
                    ),
                    AIMedia(
                        media_type=AIMediaType.AUDIO,
                        path="tests/media/voice.ogg",
                        filename="voice.ogg",
                        mime_type="audio/ogg",
                        metadata={"telegram_kind": "voice"},
                    ),
                ],
                response_format="plain_text",
            ),
        ),
        (
            "text_file_plus_prompt",
            AIRequest(
                text="Прочитай текстовый файл и сделай краткое резюме.",
                instructions="Ответь списком.",
                text_files=[
                    AITextFile(
                        filename="source.txt",
                        content="Текст внутри файла.",
                    )
                ],
                response_format="plain_text",
            ),
        ),
    ]

    for case_name, request in cases:
        messages = packer.build_messages(request)

        print("=" * 80)
        print(case_name)
        print("=" * 80)

        print(
            json.dumps(
                serialize_messages(messages),
                ensure_ascii=False,
                indent=2,
            )
        )


def serialize_messages(messages: list[MiraTelegramOutgoingMessage]) -> list[dict]:
    result = []

    for index, message in enumerate(messages, start=1):
        result.append(
            {
                "index": index,
                "kind": message.kind.value,
                "text_preview": preview(message.text),
                "text_length": len(message.text or ""),
                "starts_with_mira": bool(
                    (message.text or "").strip().lower().startswith("мира")
                ),
                "attachments": [
                    {
                        "kind": attachment.kind.value,
                        "source": attachment.source,
                        "filename": attachment.filename,
                        "mime_type": attachment.mime_type,
                        "has_text_file": attachment.text_file is not None,
                        "text_file_length": (
                            len(attachment.text_file.content)
                            if attachment.text_file is not None
                            else 0
                        ),
                    }
                    for attachment in message.attachments
                ],
                "metadata": message.metadata,
            }
        )

    return result


def preview(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""

    value = text.replace("\n", "\\n")

    if len(value) <= limit:
        return value

    return value[:limit] + "..."


if __name__ == "__main__":
    main()
    
