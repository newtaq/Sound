import asyncio
import time
from typing import Any

from pyrogram import filters
from pyrogram.handlers import EditedMessageHandler, MessageHandler, RawUpdateHandler

from app.infrastructure.providers.mira.client import MiraTelegramClient
from app.infrastructure.providers.mira.config import load_mira_telegram_config


def extract_text(message: Any) -> str:
    text = getattr(message, "text", None)
    caption = getattr(message, "caption", None)

    if text:
        return str(text)

    if caption:
        return str(caption)

    return ""


def sender_info(message: Any) -> dict:
    sender = getattr(message, "from_user", None)

    if sender is None:
        return {}

    return {
        "id": getattr(sender, "id", None),
        "username": getattr(sender, "username", None),
        "first_name": getattr(sender, "first_name", None),
        "is_bot": getattr(sender, "is_bot", None),
    }


async def main() -> None:
    config = load_mira_telegram_config()
    client_wrapper = MiraTelegramClient(config)

    await client_wrapper.start()
    app = client_wrapper.raw_client

    stream_chat_id = client_wrapper.stream_chat_id
    await app.get_chat(stream_chat_id)

    started_at = time.monotonic()

    async def on_message(_: Any, message: Any) -> None:
        chat = getattr(message, "chat", None)
        chat_id = getattr(chat, "id", None)

        if chat_id != getattr(await app.get_chat(stream_chat_id), "id", None):
            return

        print("\nNEW MESSAGE")
        print("time:", round(time.monotonic() - started_at, 2))
        print("id:", getattr(message, "id", None))
        print("chat_id:", chat_id)
        print("sender:", sender_info(message))
        print("text:", extract_text(message))

    async def on_edited_message(_: Any, message: Any) -> None:
        chat = getattr(message, "chat", None)
        chat_id = getattr(chat, "id", None)

        if chat_id != getattr(await app.get_chat(stream_chat_id), "id", None):
            return

        print("\nEDITED MESSAGE")
        print("time:", round(time.monotonic() - started_at, 2))
        print("id:", getattr(message, "id", None))
        print("chat_id:", chat_id)
        print("sender:", sender_info(message))
        print("text:", extract_text(message))

    async def on_raw_update(_: Any, update: Any, users: Any, chats: Any) -> None:
        update_name = type(update).__name__

        if "Draft" in update_name or "Edit" in update_name or "Message" in update_name:
            print("\nRAW UPDATE")
            print("time:", round(time.monotonic() - started_at, 2))
            print("type:", update_name)
            print("update:", update)

    app.add_handler(MessageHandler(on_message, filters.private), group=50)
    app.add_handler(EditedMessageHandler(on_edited_message, filters.private), group=51)
    app.add_handler(RawUpdateHandler(on_raw_update), group=52)

    print("Sending stream test to:", stream_chat_id)

    sent = await app.send_message(
        chat_id=stream_chat_id,
        text=(
            "мира Ответь медленно в 10 коротких пунктах. "
            "Пиши так, чтобы в Telegram был виден streaming."
        ),
        disable_web_page_preview=True,
    )

    print("sent message id:", sent.id)
    print("listening for 40 seconds...")

    await asyncio.sleep(40)

    await client_wrapper.stop()


if __name__ == "__main__":
    asyncio.run(main())
    
