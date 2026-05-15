import asyncio
import json

from app.infrastructure.providers.mira.config import load_mira_telegram_config
from app.infrastructure.providers.mira.topics import MiraTelegramTopicManager


async def main() -> None:
    config = load_mira_telegram_config()
    topic_manager = MiraTelegramTopicManager(config)

    session_id = "session_topic_smoke_test"

    message_thread_id = await topic_manager.get_message_thread_id(session_id)

    print("SESSION:", session_id)
    print("MESSAGE_THREAD_ID:", message_thread_id)

    second_message_thread_id = await topic_manager.get_message_thread_id(session_id)

    print("SECOND MESSAGE_THREAD_ID:", second_message_thread_id)
    print("SAME:", message_thread_id == second_message_thread_id)

    print("\nTOPIC STORE PATH:")
    print(config.topic_store_path)

    with open(config.topic_store_path, "r", encoding="utf-8") as file:
        print(
            json.dumps(
                json.load(file),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
    
