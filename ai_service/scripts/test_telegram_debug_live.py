import asyncio
import json

from app.infrastructure import build_ai_client
from app.infrastructure.telegram_debug import load_telegram_visual_debug_config


async def main() -> None:
    config = load_telegram_visual_debug_config()

    if not config.enabled:
        raise RuntimeError(
            "Telegram visual debug is disabled. "
            "Set AI_TELEGRAM_DEBUG_ENABLED=true in .env"
        )

    if not config.bot_token:
        raise RuntimeError(
            "AI_TELEGRAM_DEBUG_BOT_TOKEN is not configured in .env"
        )

    if config.chat_id is None:
        raise RuntimeError(
            "AI_TELEGRAM_DEBUG_CHAT_ID is not configured in .env"
        )

    client = build_ai_client()

    response = await client.ask(
        text=(
            "Ответь строго одной строкой: "
            "Telegram visual debug работает."
        ),
        session_id="telegram-debug-kishlak-smoke-test",
        provider_name="groq",
        response_format="plain_text",
        use_history=False,
        save_history=False,
        metadata={
            "event_title": "КИШЛАК",
            "event_date": "2026-05-12",
            "debug_test": "telegram_visual_debug_live",
        },
    )

    await asyncio.sleep(1)

    service = getattr(client, "_service", None)
    router = getattr(service, "_provider_router", None)
    debug_sink = getattr(router, "_debug_sink", None)

    if debug_sink is not None and hasattr(debug_sink, "_telegram_sink"):
        telegram_sink = getattr(debug_sink, "_telegram_sink", None)

        if telegram_sink is not None and hasattr(telegram_sink, "flush"):
            await telegram_sink.flush()

    print("STATUS:", response.status.value)
    print("PROVIDER:", response.provider_name)
    print("REQUEST:", response.request_id)
    print("SESSION:", response.session_id)
    print("ERROR:", response.error)

    print()
    print("TEXT:")
    print(response.text)

    print()
    print("METADATA:")
    print(
        json.dumps(
            response.metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    assert response.status.value == "ok"
    assert response.text.strip()

    print()
    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
