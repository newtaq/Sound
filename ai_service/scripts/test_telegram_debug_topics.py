import asyncio
import tempfile
from pathlib import Path

from app.infrastructure.telegram_debug.config import TelegramVisualDebugConfig
from app.infrastructure.telegram_debug.topics import (
    FileTelegramDebugTopicStore,
    TelegramDebugBotApiClient,
    TelegramDebugTopicManager,
)


class FakeTelegramDebugBotApiClient(TelegramDebugBotApiClient):
    def __init__(self) -> None:
        self.created_topics: list[dict] = []
        self.edited_topics: list[dict] = []
        self.next_thread_id = 100

    async def get_forum_topic_icon_stickers(self) -> list:
        return []

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

        fake_client = FakeTelegramDebugBotApiClient()
        store = FileTelegramDebugTopicStore(str(store_path))
        manager = TelegramDebugTopicManager(
            config=config,
            store=store,
            bot_api_client=fake_client,
        )

        first = await manager.prepare_topic_for_message(
            session_id="session-kishlak",
            request_id="request-1",
            provider_name="groq",
            status="active",
            event_title="КИШЛАК",
            event_date="2026-05-12",
        )

        assert first is not None
        assert first.session_id == "session-kishlak"
        assert first.chat_id == -1001234567890
        assert first.message_thread_id == 101
        assert first.title == "#1  groq  active  2026-05-12 КИШЛАК"
        assert first.icon_custom_emoji_id is None
        assert first.metadata.get("icon_color") is not None
        assert first.metadata["message_count"] == 1
        assert first.metadata["provider_name"] == "groq"
        assert first.metadata["status"] == "active"
        assert first.metadata["event_title"] == "КИШЛАК"
        assert first.metadata["event_date"] == "2026-05-12"

        second = await manager.prepare_topic_for_message(
            session_id="session-kishlak",
            request_id="request-2",
            provider_name="groq",
            status="finished",
            event_title="КИШЛАК",
            event_date="2026-05-12",
        )

        assert second is not None
        assert second.message_thread_id == first.message_thread_id
        assert second.title == "#2  groq  finished  2026-05-12 КИШЛАК"
        assert second.metadata["message_count"] == 2
        assert second.metadata["status"] == "finished"

        assert len(fake_client.created_topics) == 1
        assert fake_client.created_topics[0]["name"] == (
            "#1  groq  active  2026-05-12 КИШЛАК"
        )
        assert fake_client.created_topics[0]["icon_custom_emoji_id"] is None
        assert fake_client.created_topics[0]["icon_color"] is not None

        assert len(fake_client.edited_topics) == 1
        assert fake_client.edited_topics[0]["name"] == (
            "#2  groq  finished  2026-05-12 КИШЛАК"
        )

        restored = store.get(
            session_id="session-kishlak",
            chat_id=-1001234567890,
        )

        assert restored is not None
        assert restored.title == second.title
        assert restored.message_thread_id == second.message_thread_id
        assert restored.icon_custom_emoji_id == second.icon_custom_emoji_id
        assert restored.metadata.get("icon_color") == second.metadata.get("icon_color")
        assert restored.metadata["message_count"] == 2

    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
