from dataclasses import dataclass, field
from typing import Any

from app.application.contracts.models import AIMedia


@dataclass(slots=True)
class AIContentInput:
    text: str

    source_type: str | None = None
    source_platform: str | None = None
    source_id: str | None = None
    source_item_id: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    published_at: str | None = None

    media: list[AIMedia] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    preprocessing: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    source_post_id: str | None = None
    

