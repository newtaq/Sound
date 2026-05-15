import asyncio
import json

from app.application.contracts import AIRequest
from app.infrastructure.providers import build_provider_router


async def main() -> None:
    router = build_provider_router(
        provider_names=[
            "groq",
            "mira_telegram",
            "content_mock",
        ]
    )

    request = AIRequest(
        text="Ответь одной короткой фразой: Groq provider работает?",
        provider_name="groq",
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
    
