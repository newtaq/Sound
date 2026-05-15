import asyncio

from app.application.contracts import AIRequest
from app.infrastructure.providers.mira import MiraTelegramProvider


async def main() -> None:
    provider = MiraTelegramProvider()

    request = AIRequest(
        text=(
            "Ответь в 10 коротких пунктах, чтобы было видно стриминг. "
            "Тема: зачем нужен отдельный Telegram-провайдер для Миры."
        ),
        session_id="mira-stream-smoke-test",
        instructions="Отвечай простым русским языком.",
        response_format="plain_text",
    )

    async for chunk in provider.stream(request):
        print("EVENT:", chunk.event_type)

        if chunk.text:
            print("DELTA:")
            print(chunk.text)

        if chunk.event_type.value in {"finished", "error"}:
            print("FULL:")
            print(chunk.full_text)

        if chunk.error:
            print("ERROR:", chunk.error)

        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(main())
    
