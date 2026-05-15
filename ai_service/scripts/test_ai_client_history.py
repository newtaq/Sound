import asyncio

from app.infrastructure import build_ai_client


async def main() -> None:
    client = build_ai_client()

    first_response = await client.ask(
        text="Запомни тестовое слово: АПЕЛЬСИН. Ответь коротко: запомнил.",
        provider_name="mira_telegram",
        instructions="Отвечай кратко.",
    )

    session_id = first_response.session_id

    print("FIRST SESSION:", session_id)
    print("FIRST TEXT:")
    print(first_response.text)

    second_response = await client.ask(
        text="Какое тестовое слово я просил тебя запомнить в прошлом сообщении?",
        session_id=session_id,
        provider_name="mira_telegram",
        instructions="Ответь только самим словом.",
    )

    print("\nSECOND SESSION:", second_response.session_id)
    print("SECOND TEXT:")
    print(second_response.text)

    history = await client.get_history(session_id=session_id)

    print("\nHISTORY:")
    for index, message in enumerate(history, start=1):
        print(f"{index}. {message.role}: {message.content}")


if __name__ == "__main__":
    asyncio.run(main())
    
