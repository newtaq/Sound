from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class TelegramDebugMessageKind(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    STREAM_STARTED = "stream_started"
    STREAM_DELTA = "stream_delta"
    STREAM_FINISHED = "stream_finished"
    ERROR = "error"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    INFO = "info"


@dataclass(slots=True)
class TelegramDebugTopic:
    session_id: str
    chat_id: int | str
    message_thread_id: int
    title: str
    emoji_key: str
    created_at: str
    updated_at: str
    icon_custom_emoji_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TelegramDebugMessage:
    kind: TelegramDebugMessageKind
    session_id: str | None
    request_id: str | None = None

    provider_name: str | None = None
    event_title: str | None = None

    text: str = ""
    full_text: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: _utc_now())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
