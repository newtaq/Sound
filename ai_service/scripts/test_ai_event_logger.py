import asyncio

from app.application.observability import (
    AIEvent,
    AIEventLevel,
    MemoryAIEventLogger,
    NullAIEventLogger,
)


async def main() -> None:
    memory_logger = MemoryAIEventLogger()
    null_logger = NullAIEventLogger()

    event = AIEvent(
        name="cache_hit",
        level=AIEventLevel.INFO,
        message="Loaded analysis result from cache",
        session_id="logger-test-1",
        provider_name="content_mock",
        metadata={
            "cache_key": "ai:analysis:test",
        },
    )

    await memory_logger.log(event)
    await null_logger.log(event)

    print("EVENTS COUNT:", len(memory_logger.events))
    print("EVENT NAME:", memory_logger.events[0].name)
    print("EVENT LEVEL:", memory_logger.events[0].level)
    print("EVENT SESSION:", memory_logger.events[0].session_id)
    print("EVENT PROVIDER:", memory_logger.events[0].provider_name)
    print("EVENT CACHE KEY:", memory_logger.events[0].metadata["cache_key"])

    if len(memory_logger.events) != 1:
        raise SystemExit("Memory logger did not store event")

    if memory_logger.events[0].name != "cache_hit":
        raise SystemExit("Invalid event name")


if __name__ == "__main__":
    asyncio.run(main())
    
