import asyncio
import json

from app.application.contracts import AIMode
from app.infrastructure.service_factory import build_ai_client


async def main() -> None:
    client = build_ai_client(
        provider_names=[
            "mira_telegram",
        ]
    )

    response = await client.ask(
        text=(
            "Ответь коротко одним предложением: "
            "тест Mira с forum topic работает."
        ),
        provider_name="mira_telegram",
        mode=AIMode.DEEP,
        session_id="mira-topic-generate-smoke-test",
        use_history=False,
        save_history=False,
        metadata={
            "script": "test_mira_topic_generate",
            "forum_topics_expected": True,
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


if __name__ == "__main__":
    asyncio.run(main())
