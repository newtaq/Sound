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

    response = await service.generate(
        AIRequest(
            text="Проверка логов generate",
            session_id="generate-events-test-1",
            provider_name="mock",
            metadata={
                "task": "test_generate_events",
            },
        )
    )

    event_names = [event.name for event in event_logger.events]

    print("RESPONSE:", response)
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

    if response.status != "ok":
        raise SystemExit("Generate response is not ok")

    if "provider_generate_started" not in event_names:
        raise SystemExit("Generate started event was not logged")

    if "provider_generate_finished" not in event_names:
        raise SystemExit("Generate finished event was not logged")

    finished_events = [
        event
        for event in event_logger.events
        if event.name == "provider_generate_finished"
    ]

    if finished_events[0].metadata.get("task") != "test_generate_events":
        raise SystemExit("Invalid task in finished event metadata")

    if "duration_ms" not in finished_events[0].metadata:
        raise SystemExit("duration_ms is missing")


if __name__ == "__main__":
    asyncio.run(main())
    
