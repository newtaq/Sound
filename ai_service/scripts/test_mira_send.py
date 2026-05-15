import asyncio

from app.infrastructure.providers.mira.client import MiraTelegramClient
from app.infrastructure.providers.mira.config import load_mira_telegram_config
from app.infrastructure.providers.mira.request_payload import (
    MiraTelegramMessageKind,
    MiraTelegramOutgoingMessage,
)


async def main() -> None:
    config = load_mira_telegram_config()
    client = MiraTelegramClient(config)

    try:
        messages = [
            MiraTelegramOutgoingMessage(
                kind=MiraTelegramMessageKind.TEXT,
                text="мира привет, это тестовое сообщение от провайдера",
                metadata={"telegram_message_role": "manual_test"},
            )
        ]

        sent_messages = await client.send_messages(messages)

        for message in sent_messages:
            print(
                {
                    "message_id": message.message_id,
                    "chat_id": message.chat_id,
                    "text": message.text,
                    "caption": message.caption,
                }
            )
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
    
