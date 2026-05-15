import asyncio
import json

from app.application.contracts import AIRequest
from app.infrastructure.providers.mira import MiraTelegramProvider


async def main() -> None:
    provider = MiraTelegramProvider()

    request = AIRequest(
        text=(
            "Ответь коротко одним предложением: "
            "получилось ли подключить Telegram-провайдер Миры?"
        ),
        session_id="mira-provider-smoke-test",
        instructions=(
            "Ты тестируешь интеграцию. "
            "Ответ должен быть коротким и без лишнего форматирования."
        ),
        response_format="plain_text",
    )

    response = await provider.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("SESSION:", response.session_id)

    if response.error:
        print("ERROR:", response.error)

    print("\nTEXT:")
    print(response.text)

    print("\nMETADATA:")
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
    
