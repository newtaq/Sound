import asyncio
import tempfile
from pathlib import Path

from app.infrastructure.telegram_debug import (
    FileTelegramDebugTopicStore,
    TelegramDebugBotApiClient,
    TelegramDebugTopicManager,
    TelegramVisualDebugConfig,
)


class FakeTelegramDebugBotApiClient(TelegramDebugBotApiClient):
    def __init__(self) -> None:
        self.created_topics: list[dict] = []
        self.next_thread_id = 400

    async def get_forum_topic_icon_stickers(self) -> list:
        return [
            {
                "emoji": "",
                "custom_emoji_id": "icon-a",
            },
            {
                "emoji": "🚀",
                "custom_emoji_id": "icon-b",
            },
            {
                "emoji": "",
                "custom_emoji_id": "icon-c",
            },
        ]

    async def create_forum_topic(
        self,
        chat_id: int | str,
        name: str,
        icon_custom_emoji_id: str | None = None,
        icon_color: int | None = None,
    ) -> int:
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


async def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        store_path = Path(temp_dir) / "telegram_debug_topics.json"

        config = TelegramVisualDebugConfig(
            enabled=True,
            bot_token="fake-token",
            chat_id=-1001234567890,
            create_topics_enabled=True,
            topic_store_path=str(store_path),
        )

        fake_client = FakeTelegramDebugBotApiClient()
        manager = TelegramDebugTopicManager(
            config=config,
            store=FileTelegramDebugTopicStore(str(store_path)),
            bot_api_client=fake_client,
        )

        topic = await manager.prepare_topic_for_message(
            session_id="session-kishlak",
            request_id="request-1",
            provider_name="groq",
            status="active",
            event_title="КИШЛАК",
            event_date="12 мая",
        )

        assert topic is not None
        assert len(fake_client.created_topics) == 1

        created = fake_client.created_topics[0]

        assert created["name"] == "#1  groq  active  12 мая КИШЛАК"
        assert created["icon_custom_emoji_id"] in {"icon-a", "icon-b", "icon-c"}
        assert created["icon_color"] is not None

        assert topic.icon_custom_emoji_id == created["icon_custom_emoji_id"]
        assert topic.metadata["icon_custom_emoji_id"] == created["icon_custom_emoji_id"]
        assert topic.metadata["icon_emoji"] in {"", "", ""}

        restored = FileTelegramDebugTopicStore(str(store_path)).get(
            session_id="session-kishlak",
            chat_id=-1001234567890,
        )

        assert restored is not None
        assert restored.icon_custom_emoji_id == topic.icon_custom_emoji_id

    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
