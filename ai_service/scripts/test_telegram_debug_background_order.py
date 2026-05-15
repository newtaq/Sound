import asyncio
import tempfile
from pathlib import Path

from app.infrastructure.telegram_debug import (
    FileTelegramDebugTopicStore,
    TelegramDebugBotApiClient,
    TelegramDebugMessage,
    TelegramDebugMessageKind,
    TelegramDebugTopicManager,
    TelegramVisualDebugConfig,
    TelegramVisualDebugSink,
)


class SlowFakeTelegramDebugBotApiClient(TelegramDebugBotApiClient):
    def __init__(self) -> None:
        self.created_topics: list[dict] = []
        self.edited_topics: list[dict] = []
        self.sent_messages: list[dict] = []
        self.next_thread_id = 500
        self.next_message_id = 1000

    async def get_forum_topic_icon_stickers(self) -> list:
        return [
            {
                "emoji": "🎸",
                "custom_emoji_id": "icon-rock",
            }
        ]

    async def create_forum_topic(
        self,
        chat_id: int | str,
        name: str,
        icon_custom_emoji_id: str | None = None,
        icon_color: int | None = None,
    ) -> int:
        await asyncio.sleep(0.05)
        self.next_thread_id += 1

        self.created_topics.append(
            {
                "chat_id": chat_id,
                "name": name,
                "icon_custom_emoji_id": icon_custom_emoji_id,
                "icon_color": icon_color,
                "message_thread_id": self.next_thread_id,
            }
        )

        return self.next_thread_id

    async def edit_forum_topic(
        self,
        chat_id: int | str,
        message_thread_id: int,
        name: str | None = None,
        icon_custom_emoji_id: str | None = None,
    ) -> None:
        self.edited_topics.append(
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "name": name,
                "icon_custom_emoji_id": icon_custom_emoji_id,
            }
        )

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        message_thread_id: int | None = None,
        disable_web_page_preview: bool = True,
        parse_mode: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        await asyncio.sleep(0.01)
        self.next_message_id += 1

        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "text": text,
                "message_id": self.next_message_id,
                "parse_mode": parse_mode,
                "reply_to_message_id": reply_to_message_id,
            }
        )

        return self.next_message_id


async def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        store_path = Path(temp_dir) / "telegram_debug_topics.json"

        config = TelegramVisualDebugConfig(
            enabled=True,
            bot_token="fake-token",
            chat_id=-1001234567890,
            create_topics_enabled=True,
            topic_store_path=str(store_path),
            topic_name_prefix="",
        )

        fake_client = SlowFakeTelegramDebugBotApiClient()
        topic_manager = TelegramDebugTopicManager(
            config=config,
            store=FileTelegramDebugTopicStore(str(store_path)),
            bot_api_client=fake_client,
        )
        sink = TelegramVisualDebugSink(
            config=config,
            topic_manager=topic_manager,
            bot_api_client=fake_client,
        )

        request = TelegramDebugMessage(
            kind=TelegramDebugMessageKind.REQUEST,
            session_id="session-kishlak",
            request_id="request-1",
            provider_name="groq",
            event_title="КИШЛАК",
            text="request text",
            metadata={
                "event_date": "2026-05-12",
            },
        )
        response = TelegramDebugMessage(
            kind=TelegramDebugMessageKind.RESPONSE,
            session_id="session-kishlak",
            request_id="request-1",
            provider_name="groq",
            event_title="КИШЛАК",
            text="response text",
            metadata={
                "event_date": "2026-05-12",
                "status": "finished",
            },
        )

        sink.emit_background(request)
        sink.emit_background(response)

        await asyncio.sleep(0.5)

        assert len(fake_client.created_topics) == 1
        assert fake_client.created_topics[0]["name"] == (
            "#1  groq  active  2026-05-12 КИШЛАК"
        )

        assert len(fake_client.edited_topics) == 1
        assert fake_client.edited_topics[0]["name"] == (
            "#2  groq  finished  2026-05-12 КИШЛАК"
        )

        assert len(fake_client.sent_messages) == 2
        assert "request" in fake_client.sent_messages[0]["text"]
        assert "response" in fake_client.sent_messages[1]["text"]

        restored = FileTelegramDebugTopicStore(str(store_path)).get(
            session_id="session-kishlak",
            chat_id=-1001234567890,
        )

        assert restored is not None
        assert restored.title == "#2  groq  finished  2026-05-12 КИШЛАК"
        assert restored.metadata["message_count"] == 2

    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
