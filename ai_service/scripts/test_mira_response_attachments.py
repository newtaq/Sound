import asyncio
import json

from app.infrastructure import build_ai_client


async def main() -> None:
    client = build_ai_client()

    response = await client.ask(
        text=(
            "Отправь в ответ любой небольшой файл .txt с caption. "
            "Внутри файла напиши: test attachment from mira. "
            "Caption сделай: файл отправлен."
        ),
        provider_name="mira_telegram",
        instructions=(
            "Важно: ответь именно файлом, если можешь. "
            "Если файл отправить нельзя, отправь gif или картинку с caption."
        ),
        response_format="plain_text",
    )

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("SESSION:", response.session_id)
    print("ERROR:", response.error)

    print("\nTEXT:")
    print(response.text)

    print("\nATTACHMENTS:")
    for index, attachment in enumerate(response.attachments, start=1):
        print(f"[{index}]")
        print(
            json.dumps(
                {
                    "kind": attachment.kind,
                    "media_id": attachment.media_id,
                    "file_unique_id": attachment.file_unique_id,
                    "filename": attachment.filename,
                    "mime_type": attachment.mime_type,
                    "file_size": attachment.file_size,
                    "caption": attachment.caption,
                    "telegram_chat_id": attachment.telegram_chat_id,
                    "telegram_message_id": attachment.telegram_message_id,
                    "metadata": attachment.metadata,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    print("\nMETADATA:")
    print(
        json.dumps(
            response.metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
    
