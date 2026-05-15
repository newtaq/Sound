import asyncio
import json

from app.application.contracts import AIRequest
from app.infrastructure.providers import build_provider_router


async def main() -> None:
    router = build_provider_router(
        provider_names=[
            "groq_search",
            "groq",
            "content_mock",
        ]
    )

    request = AIRequest(
        text=(
            "Найди через интернет актуальную информацию и ответь коротко: "
            "какая сейчас последняя стабильная версия Python? "
            "Укажи версию и дату релиза, если найдёшь."
        ),
        provider_name="groq_search",
        instructions=(
            "Используй web search, если он доступен. "
            "Ответь кратко и укажи источник/ссылку, если модель его вернула."
        ),
        response_format="plain_text",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("SESSION:", response.session_id)
    print("REQUEST:", response.request_id)
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
    
