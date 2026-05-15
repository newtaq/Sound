import json

from app.application.prompts import JSON_REPAIR_RULES, JSON_REPAIR_TASK


class JsonRepairPromptBuilder:
    def build(
        self,
        broken_text: str,
        parse_error: str | None = None,
    ) -> str:
        payload = {
            "task": JSON_REPAIR_TASK,
            "rules": JSON_REPAIR_RULES,
            "parse_error": parse_error,
            "broken_response": broken_text,
            "expected_output": {
                "content_type": "string",
                "is_useful": "boolean",
                "priority": "string",
                "confidence": "number from 0 to 1",
                "main_decision": "string",
                "decisions": [
                    {
                        "type": "string",
                        "confidence": "number from 0 to 1",
                        "data": {},
                    }
                ],
                "variants": [],
                "sql_plan": [],
                "warnings": [],
            },
        }

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    

