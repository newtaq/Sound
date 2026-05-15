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


class FakeTelegramDebugBotApiClient(TelegramDebugBotApiClient):
    def __init__(self) -> None:
        self.created_topics: list[dict] = []
        self.sent_messages: list[dict] = []
        self.next_thread_id = 200
        self.next_message_id = 1000

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

    async def get_forum_topic_icon_stickers(self) -> list:
        return [
            {
                "emoji": "",
                "custom_emoji_id": "debug_icon_1",
            },
            {
                "emoji": "",
                "custom_emoji_id": "debug_icon_2",
            },
        ]

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        message_thread_id: int | None = None,
        disable_web_page_preview: bool = True,
        parse_mode: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        self.next_message_id += 1

        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "message_thread_id": message_thread_id,
                "disable_web_page_preview": disable_web_page_preview,
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
            topic_name_prefix="AI debug",
            max_message_length=700,
        )

        fake_client = FakeTelegramDebugBotApiClient()

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

        await sink.emit(
            TelegramDebugMessage(
                kind=TelegramDebugMessageKind.REQUEST,
                session_id="session-kishlak",
                request_id="request-1",
                provider_name="groq",
                event_title="КИШЛАК",
                text="Собери черновик афиши.",
                metadata={
                    "event_date": "2026-05-12",
                    "mode": "deep",
                },
            )
        )

        await sink.emit(
            TelegramDebugMessage(
                kind=TelegramDebugMessageKind.RESPONSE,
                session_id="session-kishlak",
                request_id="request-1",
                provider_name="groq",
                event_title="КИШЛАК",
                text="Черновик готов.",
                metadata={
                    "status": "ok",
                },
            )
        )

        assert len(fake_client.created_topics) == 1
        assert len(fake_client.sent_messages) == 2

        first_thread_id = fake_client.sent_messages[0]["message_thread_id"]
        second_thread_id = fake_client.sent_messages[1]["message_thread_id"]

        assert first_thread_id is not None
        assert first_thread_id == second_thread_id

        first_text = fake_client.sent_messages[0]["text"]
        second_text = fake_client.sent_messages[1]["text"]

        assert " request" in first_text
        assert "Собери черновик афиши." in first_text
        assert "session-kishlak" in first_text
        assert "КИШЛАК" in first_text

        assert "<b>" in second_text
        assert "Черновик готов." in second_text
        assert "status" in second_text

    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
