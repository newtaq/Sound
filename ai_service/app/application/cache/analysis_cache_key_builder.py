import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from app.application.contracts import AIContentInput


class AIAnalysisCacheKeyBuilder:
    def build_content_key(
        self,
        content: AIContentInput,
        provider_name: str | None = None,
    ) -> str:
        source_item_id = content.source_item_id or content.source_post_id

        payload = {
            "kind": "analysis_result",
            "provider_name": provider_name,
            "content": {
                "text": content.text,
                "source_type": content.source_type,
                "source_platform": content.source_platform,
                "source_id": content.source_id,
                "source_item_id": source_item_id,
                "source_url": content.source_url,
                "source_name": content.source_name,
                "published_at": content.published_at,
                "links": content.links,
                "media": [
                    self._to_jsonable(media)
                    for media in content.media
                ],
                "preprocessing": content.preprocessing,
                "metadata": content.metadata,
            },
        }

        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )

        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        return f"ai:analysis:{digest}"

    def _to_jsonable(self, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)

        return value
    

