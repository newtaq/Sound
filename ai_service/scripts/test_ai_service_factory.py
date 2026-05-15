import asyncio
import json

from app.application.contracts import AIRequest
from app.infrastructure import build_ai_service


async def main() -> None:
    service = build_ai_service()

    request = AIRequest(
        text="Ответь одной короткой фразой: сообщение через AIService получено?",
        provider_name="mira_telegram",
        instructions="Ответь только: Да, сообщение через AIService получено.",
        response_format="plain_text",
    )

    print("REQUEST SESSION:", request.session_id)

    response = await service.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("RESPONSE SESSION:", response.session_id)

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
    
