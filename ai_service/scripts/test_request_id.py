import asyncio
import json

from app.infrastructure import build_ai_client


async def main() -> None:
    client = build_ai_client()

    first_response = await client.ask(
        text="Ответь коротко: первый запрос с request_id получен?",
        provider_name="mira_telegram",
        instructions="Ответь одной короткой фразой.",
        response_format="plain_text",
    )

    second_response = await client.ask(
        text="Ответь коротко: второй запрос в той же сессии получен?",
        session_id=first_response.session_id,
        provider_name="mira_telegram",
        instructions="Ответь одной короткой фразой.",
        response_format="plain_text",
    )

    print("FIRST SESSION:", first_response.session_id)
    print("FIRST REQUEST:", first_response.request_id)
    print("FIRST TEXT:", first_response.text)

    print("\nSECOND SESSION:", second_response.session_id)
    print("SECOND REQUEST:", second_response.request_id)
    print("SECOND TEXT:", second_response.text)

    print("\nSAME SESSION:", first_response.session_id == second_response.session_id)
    print("DIFFERENT REQUESTS:", first_response.request_id != second_response.request_id)

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
    
