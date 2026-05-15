import asyncio
import json

from app.application.contracts import AITextFile
from app.infrastructure import build_ai_client


async def main() -> None:
    client = build_ai_client()

    response = await client.ask(
        text=(
            "Прочитай уже отправленный текстовый файл и ответь только значением "
            "поля secret_word."
        ),
        provider_name="mira_telegram",
        text_files=[
            AITextFile(
                filename="input_context_secret_word.txt",
                content=(
                    "Это входной файл для анализа.\n"
                    "secret_word=ГРЕЙПФРУТ\n"
                    "Не нужно создавать новые файлы или медиа.\n"
                ),
            )
        ],
        instructions="Ответь только одним словом из файла.",
        response_format="plain_text",
    )

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("SESSION:", response.session_id)
    print("ERROR:", response.error)

    print("\nTEXT:")
    print(response.text)

    print("\nATTACHMENTS FROM MIRA:")
    for attachment in response.attachments:
        print(
            json.dumps(
                {
                    "kind": attachment.kind,
                    "filename": attachment.filename,
                    "mime_type": attachment.mime_type,
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
    
