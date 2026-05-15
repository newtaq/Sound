import asyncio

from app.infrastructure.providers.mira.client import MiraTelegramClient
from app.infrastructure.providers.mira.config import load_mira_telegram_config


async def main() -> None:
    config = load_mira_telegram_config()
    client = MiraTelegramClient(config)

    try:
        await client.start()

        print("Dialogs:")
        print("-" * 80)

        async for dialog in client.raw_client.get_dialogs(limit=100):
            chat = dialog.chat

            chat_id = getattr(chat, "id", None)
            title = getattr(chat, "title", None)
            username = getattr(chat, "username", None)
            first_name = getattr(chat, "first_name", None)
            last_name = getattr(chat, "last_name", None)
            chat_type = getattr(chat, "type", None)

            name_parts = [
                str(value)
                for value in [title, first_name, last_name]
                if value
            ]

            name = " ".join(name_parts) or "no_name"

            print(
                {
                    "id": chat_id,
                    "type": str(chat_type),
                    "name": name,
                    "username": username,
                }
            )

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
    
