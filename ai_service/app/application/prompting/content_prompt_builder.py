import json

from app.application.contracts import AIContentInput, AIContentRegistry
from app.application.prompts import CONTENT_ANALYSIS_RULES, CONTENT_ANALYSIS_TASK


class ContentPromptBuilder:
    def __init__(self, content_registry: AIContentRegistry | None = None) -> None:
        self._content_registry = content_registry or AIContentRegistry()

    def build(self, content: AIContentInput) -> str:
        content_types = " | ".join(self._content_registry.content_types)
        priorities = " | ".join(self._content_registry.priorities)
        decisions = " | ".join(self._content_registry.decision_types)

        source_item_id = content.source_item_id or content.source_post_id

        payload = {
            "task": CONTENT_ANALYSIS_TASK,
            "rules": CONTENT_ANALYSIS_RULES,
            "content": {
                "text": content.text,
                "source": {
                    "type": content.source_type,
                    "platform": content.source_platform,
                    "id": content.source_id,
                    "item_id": source_item_id,
                    "url": content.source_url,
                    "name": content.source_name,
                    "published_at": content.published_at,
                },
                "links": content.links,
                "media_count": len(content.media),
                "preprocessing": content.preprocessing,
                "metadata": content.metadata,
            },
            "output_schema": {
                "content_type": content_types,
                "is_useful": "boolean",
                "priority": priorities,
                "confidence": "number from 0 to 1",
                "main_decision": decisions,
                "decisions": [
                    {
                        "type": decisions,
                        "confidence": "number from 0 to 1",
                        "data": {},
                        "evidence": [
                            {
                                "field": "string, for example artist/date/city/venue/ticket_url/status",
                                "value": "extracted value",
                                "source": "text | link | media | preprocessing | db_context | metadata",
                                "source_text": "exact short fragment that supports the value",
                                "confidence": "number from 0 to 1",
                                "metadata": {},
                            }
                        ],
                    }
                ],
                "variants": [],
                "sql_plan": [],
                "warnings": [],
            },
        }

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    

