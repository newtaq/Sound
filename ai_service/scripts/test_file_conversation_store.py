import asyncio
from pathlib import Path

from app.infrastructure import build_ai_client


async def main() -> None:
    client = build_ai_client()

    first_response = await client.ask(
        text="Запомни тестовое слово для файловой истории: МАНДАРИН. Ответь: запомнил.",
        provider_name="mira_telegram",
        instructions="Отвечай кратко.",
    )

    session_id = first_response.session_id

    print("SESSION:", session_id)
    print("FIRST TEXT:")
    print(first_response.text)

    session_file = Path(".runtime/ai_sessions") / f"{session_id}.json"

    print("\nSESSION FILE:")
    print(session_file)
    print("EXISTS:", session_file.exists())

    second_client = build_ai_client()

    second_response = await second_client.ask(
        text="Какое слово я просил запомнить в этой session_id?",
        session_id=session_id,
        provider_name="mira_telegram",
        instructions="Ответь только самим словом.",
    )

    print("\nSECOND TEXT:")
    print(second_response.text)

    print("\nSESSION FILE EXISTS AFTER SECOND CLIENT:", session_file.exists())


if __name__ == "__main__":
    asyncio.run(main())
    
