import asyncio
import json

from app.infrastructure import build_ai_client


async def main() -> None:
    client = build_ai_client()

    first_response = await client.ask(
        text="Ответь коротко: первое сообщение через AIClient получено?",
        provider_name="mira_telegram",
        instructions="Ответь одной короткой фразой.",
    )

    print("FIRST STATUS:", first_response.status)
    print("FIRST PROVIDER:", first_response.provider_name)
    print("FIRST SESSION:", first_response.session_id)
    print("FIRST TEXT:")
    print(first_response.text)

    second_response = await client.ask(
        text="Ответь коротко: это второе сообщение в той же session_id?",
        session_id=first_response.session_id,
        provider_name="mira_telegram",
        instructions="Ответь одной короткой фразой.",
    )

    print("\nSECOND STATUS:", second_response.status)
    print("SECOND PROVIDER:", second_response.provider_name)
    print("SECOND SESSION:", second_response.session_id)
    print("SECOND TEXT:")
    print(second_response.text)

    print("\nSECOND METADATA:")
    print(
        json.dumps(
            second_response.metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
    
