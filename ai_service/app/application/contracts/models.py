from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.application.contracts.enums import (
    AIMediaType,
    AIMode,
    AIMessageRole,
    AIResponseStatus,
    AIStreamEventType,
)


@dataclass(slots=True)
class AIMedia:
    media_type: AIMediaType
    media_id: str | None = None
    path: str | None = None
    url: str | None = None
    mime_type: str | None = None
    filename: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AITextFile:
    filename: str
    content: str
    mime_type: str = "text/plain"


@dataclass(slots=True)
class AIMessage:
    role: AIMessageRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIProviderCapabilities:
    can_stream: bool = False
    can_stream_message_edits: bool = False
    can_analyze_images: bool = False
    can_search_web_natively: bool = False
    can_use_files: bool = False
    max_media_count: int = 0
    max_text_length: int | None = None


@dataclass(slots=True)
class AIRequest:
    text: str
    session_id: str | None = None
    request_id: str | None = None
    mode: AIMode = AIMode.DEEP
    instructions: str | None = None
    history: list[AIMessage] = field(default_factory=list)
    media: list[AIMedia] = field(default_factory=list)
    text_files: list[AITextFile] = field(default_factory=list)
    provider_name: str | None = None
    response_format: str = "compact_json"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.request_id is None:
            self.request_id = f"request_{uuid4().hex}"


@dataclass(slots=True)
class AIResponseAttachment:
    kind: str
    media_id: str | None = None
    file_unique_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    caption: str | None = None
    telegram_chat_id: int | str | None = None
    telegram_message_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIResponse:
    status: AIResponseStatus
    text: str
    provider_name: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    raw_messages: list[str] = field(default_factory=list)
    attachments: list[AIResponseAttachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class AIStreamChunk:
    event_type: AIStreamEventType
    text: str = ""
    full_text: str = ""
    provider_name: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    attachments: list[AIResponseAttachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    

