from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol


class AIEventLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class AIEvent:
    name: str
    level: AIEventLevel = AIEventLevel.INFO
    message: str | None = None
    session_id: str | None = None
    provider_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AIEventLogger(Protocol):
    async def log(self, event: AIEvent) -> None:
        pass


class NullAIEventLogger:
    async def log(self, event: AIEvent) -> None:
        return None


class MemoryAIEventLogger:
    def __init__(self) -> None:
        self.events: list[AIEvent] = []

    async def log(self, event: AIEvent) -> None:
        self.events.append(event)
        

