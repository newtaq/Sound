import asyncio
import json

from app.application.contracts import AIRequest
from app.infrastructure.providers import (
    build_ai_providers,
    build_provider_router,
    load_enabled_provider_names,
)


async def main() -> None:
    provider_names = load_enabled_provider_names()
    providers = build_ai_providers(provider_names)
    router = build_provider_router(provider_names)

    print("PROVIDER_NAMES:", provider_names)
    print("BUILT_PROVIDERS:", [provider.name for provider in providers])

    request = AIRequest(
        text="Ответь одной короткой фразой: сообщение получено?",
        session_id="provider-factory-smoke-test",
        provider_name="mira_telegram",
        instructions="Ответь только: Да, сообщение получено.",
        response_format="plain_text",
    )

    response = await router.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("TEXT:")
    print(response.text)

    print("METADATA:")
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
    
