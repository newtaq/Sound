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
        self.edited_topics: list[dict] = []
        self.sent_messages: list[dict] = []
        self.pinned_messages: list[dict] = []
        self.next_thread_id = 900
        self.next_message_id = 3000

    async def get_forum_topic_icon_stickers(self) -> list:
        return [
            {
                "emoji": "",
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

    async def pin_chat_message(
        self,
        chat_id: int | str,
        message_id: int,
        disable_notification: bool = True,
    ) -> None:
        self.pinned_messages.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "disable_notification": disable_notification,
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
                text="request <text>",
                metadata={
                    "event_date": "2026-05-12",
                    "unsafe": "<tag>",
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
                text="response <text>",
                metadata={
                    "event_date": "2026-05-12",
                    "status": "ok",
                },
            )
        )

        assert len(fake_client.sent_messages) == 2
        assert len(fake_client.pinned_messages) == 1

        request_message = fake_client.sent_messages[0]
        response_message = fake_client.sent_messages[1]

        assert request_message["parse_mode"] == "HTML"
        assert response_message["parse_mode"] == "HTML"

        assert "<b>request &lt;text&gt;</b>" in request_message["text"]
        assert "<blockquote expandable>" in request_message["text"]
        assert "&lt;tag&gt;" in request_message["text"]

        assert "<b>response &lt;text&gt;</b>" in response_message["text"]
        assert response_message["reply_to_message_id"] == request_message["message_id"]

        assert fake_client.pinned_messages[0]["message_id"] == request_message["message_id"]
        assert fake_client.edited_topics[-1]["name"] == (
            "#2  groq  ok  2026-05-12 КИШЛАК"
        )

    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
