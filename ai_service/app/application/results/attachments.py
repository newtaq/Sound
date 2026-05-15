from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AIResultAttachmentType(StrEnum):
    TEXT = "text"
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    BINARY = "binary"


@dataclass(slots=True)
class AIResultAttachment:
    filename: str
    mime_type: str
    attachment_type: AIResultAttachmentType
    content: bytes
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        return len(self.content)


@dataclass(slots=True)
class AIResultWithAttachments:
    text: str
    attachments: list[AIResultAttachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0
    

