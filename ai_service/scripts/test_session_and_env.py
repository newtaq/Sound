import asyncio
import json

from app.application.contracts import AIRequest
from app.infrastructure.providers import build_provider_router


async def main() -> None:
    router = build_provider_router()

    first_request = AIRequest(
        text="Ответь коротко: первое сообщение получено?",
        provider_name="mira_telegram",
        instructions="Ответь одной короткой фразой.",
        response_format="plain_text",
    )

    print("FIRST REQUEST SESSION:", first_request.session_id)

    first_response = await router.generate(first_request)

    print("FIRST RESPONSE SESSION:", first_response.session_id)
    print("FIRST PROVIDER:", first_response.provider_name)
    print("FIRST TEXT:")
    print(first_response.text)

    second_request = AIRequest(
        text="Ответь коротко: это второе сообщение в той же session_id?",
        session_id=first_response.session_id,
        provider_name="mira_telegram",
        instructions="Ответь одной короткой фразой.",
        response_format="plain_text",
    )

    print("\nSECOND REQUEST SESSION:", second_request.session_id)

    second_response = await router.generate(second_request)

    print("SECOND RESPONSE SESSION:", second_response.session_id)
    print("SECOND PROVIDER:", second_response.provider_name)
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
    
