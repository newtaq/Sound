import asyncio
import json
import os

from app.application.contracts import AIMode
from app.infrastructure.service_factory import build_ai_client


async def main() -> None:
    os.environ["AI_PROVIDER_MIRA_TELEGRAM_FORUM_TOPICS_ENABLED"] = "false"

    client = build_ai_client(
        provider_names=[
            "mira_telegram",
        ]
    )

    response = await client.ask(
        text=(
            "Ответь коротко одним предложением: "
            "тест Mira без forum topic работает."
        ),
        provider_name="mira_telegram",
        mode=AIMode.STANDARD,
        session_id="mira-without-topic-smoke-test",
        use_history=False,
        save_history=False,
        metadata={
            "script": "test_mira_without_topic",
            "forum_topics_expected": False,
        },
    )

    print("STATUS:", response.status.value)
    print("PROVIDER:", response.provider_name)
    print("REQUEST:", response.request_id)
    print("SESSION:", response.session_id)
    print("ERROR:", response.error)
    print()
    print("TEXT:")
    print(response.text)
    print()
    print("METADATA:")
    print(
        json.dumps(
            response.metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    assert response.status.value == "ok"
    assert response.metadata.get("message_thread_id") is None
    assert response.metadata.get("topic_status_updated") is False


if __name__ == "__main__":
    asyncio.run(main())
