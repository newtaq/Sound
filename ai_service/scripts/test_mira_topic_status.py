import asyncio
import json
import tempfile
from pathlib import Path

from app.application.contracts import AIMode
from app.infrastructure.providers.mira.config import MiraTelegramProviderConfig
from app.infrastructure.providers.mira.topics import (
    FileMiraTelegramTopicStore,
    MiraTelegramTopicManager,
)


class FakeMiraTopicBotApiClient:
    def __init__(self) -> None:
        self.next_thread_id = 100
        self.created_topics = []
        self.edited_topics = []
        self.deleted_messages = []

    async def create_forum_topic(
        self,
        chat_id: str | int,
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
        chat_id: str | int,
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

    async def delete_message(
        self,
        chat_id: str | int,
        message_id: int,
    ) -> None:
        self.deleted_messages.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
            }
        )

    async def get_forum_topic_icon_stickers(self) -> list:
        return []


async def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        store_path = Path(temp_dir) / "mira_topics.json"

        config = MiraTelegramProviderConfig(
            bot_token="fake-token",
            chat_id=-1001234567890,
            forum_topics_enabled=True,
            topic_store_path=str(store_path),
        )

        fake_bot = FakeMiraTopicBotApiClient()
        store = FileMiraTelegramTopicStore(store_path)

        manager = MiraTelegramTopicManager(
            config=config,
            store=store,
            bot_api_client=fake_bot,
        )

        thread_id = await manager.register_request(
            session_id="session_test_topic_status",
            mode=AIMode.DEEP,
            status="active",
            request_id="request_1",
        )

        assert thread_id == 101

        active_topic = await store.get_topic("session_test_topic_status")
        assert active_topic is not None
        assert active_topic.status == "active"
        assert active_topic.request_count == 1
        assert active_topic.last_request_id == "request_1"

        finished_thread_id = await manager.update_request_status(
            session_id="session_test_topic_status",
            status="finished",
            mode=AIMode.DEEP,
            request_id="request_1",
        )

        assert finished_thread_id == 101

        finished_topic = await store.get_topic("session_test_topic_status")
        assert finished_topic is not None
        assert finished_topic.status == "finished"
        assert finished_topic.last_request_id == "request_1"
        assert "finished" in finished_topic.name

        error_thread_id = await manager.update_request_status(
            session_id="session_test_topic_status",
            status="error",
            mode=AIMode.DEEP,
            request_id="request_2",
        )

        assert error_thread_id == 101

        error_topic = await store.get_topic("session_test_topic_status")
        assert error_topic is not None
        assert error_topic.status == "error"
        assert error_topic.last_request_id == "request_2"
        assert "error" in error_topic.name

        missing_thread_id = await manager.update_request_status(
            session_id="unknown_session",
            status="finished",
            mode=AIMode.STANDARD,
            request_id="request_missing",
        )

        assert missing_thread_id is None

        disabled_config = MiraTelegramProviderConfig(
            bot_token="fake-token",
            chat_id=-1001234567890,
            forum_topics_enabled=False,
            topic_store_path=str(store_path),
        )

        disabled_manager = MiraTelegramTopicManager(
            config=disabled_config,
            store=store,
            bot_api_client=fake_bot,
        )

        disabled_thread_id = await disabled_manager.update_request_status(
            session_id="session_test_topic_status",
            status="finished",
            mode=AIMode.STANDARD,
            request_id="request_disabled",
        )

        assert disabled_thread_id is None

        print(
            json.dumps(
                {
                    "thread_id": thread_id,
                    "final_status": error_topic.status,
                    "created_topics": fake_bot.created_topics,
                    "edited_topics": fake_bot.edited_topics,
                    "deleted_messages": fake_bot.deleted_messages,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print("ok")


if __name__ == "__main__":
    asyncio.run(main())
