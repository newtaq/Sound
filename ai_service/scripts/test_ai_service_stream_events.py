import asyncio

from app.application.ai_service import AIService
from app.application.contracts import AIRequest
from app.application.observability import MemoryAIEventLogger
from app.application.provider_router import AIProviderRouter
from app.infrastructure.providers.mock import MockAIProvider


async def main() -> None:
    event_logger = MemoryAIEventLogger()

    service = AIService(
        provider_router=AIProviderRouter(
            providers=[
                MockAIProvider(),
            ]
        ),
        event_logger=event_logger,
    )

    chunks = []

    async for chunk in service.stream(
        AIRequest(
            text="Проверка логов stream",
            session_id="stream-events-test-1",
            provider_name="mock",
            metadata={
                "task": "test_stream_events",
            },
        )
    ):
        chunks.append(chunk)

    event_names = [event.name for event in event_logger.events]

    print("CHUNKS COUNT:", len(chunks))
    print("EVENTS COUNT:", len(event_logger.events))
    print("EVENT NAMES:", event_names)

    for event in event_logger.events:
        print(
            "EVENT:",
            event.name,
            event.level,
            event.session_id,
            event.provider_name,
            event.metadata,
        )

    if len(chunks) == 0:
        raise SystemExit("No stream chunks received")

    if "provider_stream_started" not in event_names:
        raise SystemExit("Stream started event was not logged")

    if "provider_stream_finished" not in event_names:
        raise SystemExit("Stream finished event was not logged")

    finished_events = [
        event
        for event in event_logger.events
        if event.name == "provider_stream_finished"
    ]

    if finished_events[0].metadata.get("task") != "test_stream_events":
        raise SystemExit("Invalid task in stream finished event metadata")

    if finished_events[0].metadata.get("chunks_count") != len(chunks):
        raise SystemExit("Invalid chunks count in stream finished event")

    if "duration_ms" not in finished_events[0].metadata:
        raise SystemExit("duration_ms is missing")


if __name__ == "__main__":
    asyncio.run(main())
    
