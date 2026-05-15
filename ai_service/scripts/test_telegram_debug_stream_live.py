import asyncio
import json

from app.application.contracts import AIStreamEventType
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

    event_counts: dict[str, int] = {}
    full_text = ""
    final_metadata = {}

    async for chunk in client.stream(
        text=(
            "Ответь строго одной короткой строкой: "
            "Telegram visual debug stream работает."
        ),
        session_id="telegram-debug-stream-kishlak-smoke-test",
        provider_name="groq",
        response_format="plain_text",
        use_history=False,
        metadata={
            "event_title": "КИШЛАК STREAM",
            "event_date": "2026-05-12",
            "debug_test": "telegram_visual_debug_stream_live",
        },
    ):
        event_counts[chunk.event_type.value] = (
            event_counts.get(chunk.event_type.value, 0) + 1
        )

        if chunk.text:
            print("DELTA:", chunk.text)

        if chunk.full_text:
            full_text = chunk.full_text

        if chunk.event_type in {
            AIStreamEventType.FINISHED,
            AIStreamEventType.ERROR,
        }:
            final_metadata = chunk.metadata

        if chunk.error:
            print("ERROR:", chunk.error)

    await asyncio.sleep(1)

    service = getattr(client, "_service", None)
    router = getattr(service, "_provider_router", None)
    debug_sink = getattr(router, "_debug_sink", None)

    if debug_sink is not None and hasattr(debug_sink, "_telegram_sink"):
        telegram_sink = getattr(debug_sink, "_telegram_sink", None)

        if telegram_sink is not None and hasattr(telegram_sink, "flush"):
            await telegram_sink.flush()

    print()
    print("FULL:")
    print(full_text)

    print()
    print("EVENT_COUNTS:", event_counts)

    print()
    print("FINAL_METADATA:")
    print(
        json.dumps(
            final_metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    assert event_counts.get("started") == 1
    assert event_counts.get("finished") == 1
    assert full_text.strip()

    print()
    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
