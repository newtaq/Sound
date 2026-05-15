import json

from app.application.agent_core.evidence import AgentEvidenceSet
from app.application.agent_core.tools import AgentToolOutput


class PosterAgentVerificationPromptBuilder:
    def build_prompt(
        self,
        goal: str,
        tool_outputs: list[AgentToolOutput],
        evidence_set: AgentEvidenceSet,
    ) -> str:
        return (
            "Собери структурированный результат проверки афиши.\n\n"
            "Ответ должен быть строго JSON без markdown и без текста вокруг.\n\n"
            "JSON-схема результата:\n"
            "{\n"
            '  "title": "название события или null",\n'
            '  "event_type": "concert|festival|party|performance|meetup|other или null",\n'
            '  "artists": ["артист 1"],\n'
            '  "organizers": ["организатор 1"],\n'
            '  "age_limit": 16,\n'
            '  "description": "краткое описание или null",\n'
            '  "occurrences": [\n'
            "    {\n"
            '      "city_name": "город или null",\n'
            '      "venue_name": "площадка или null",\n'
            '      "address": "адрес или null",\n'
            '      "event_date": "YYYY-MM-DD только если год явно указан во входе/источнике, иначе исходная дата или null",\n'
            '      "start_time": "HH:MM или null",\n'
            '      "doors_time": "HH:MM или null",\n'
            '      "confidence": 0.0,\n'
            '      "verified": false,\n'
            '      "source_url": "url или null",\n'
            '      "explanation": "пояснение или null"\n'
            "    }\n"
            "  ],\n"
            '  "links": [\n'
            "    {\n"
            '      "url": "https://...",\n'
            '      "kind": "ticket|official|social|source|unknown",\n'
            '      "title": "заголовок или null",\n'
            '      "verified": false,\n'
            '      "confidence": 0.0,\n'
            '      "source_type": "input_text|ocr|qr|url|search|database|media_search|manual|unknown",\n'
            '      "explanation": "пояснение или null"\n'
            "    }\n"
            "  ],\n"
            '  "facts": [\n'
            "    {\n"
            '      "field": "date|city|venue|artist|ticket_link|source|age_limit|other",\n'
            '      "value": "значение",\n'
            '      "status": "input|candidate|verified|unverified|conflicted|rejected",\n'
            '      "source_type": "input_text|ocr|qr|url|search|database|media_search|manual|unknown",\n'
            '      "confidence": 0.0,\n'
            '      "source_url": "url или null",\n'
            '      "source_title": "название источника или null",\n'
            '      "explanation": "пояснение или null"\n'
            "    }\n"
            "  ],\n"
            '  "missing_fields": ["только реально отсутствующие поля"],\n'
            '  "conflicts": ["конфликт"],\n'
            '  "warnings": ["предупреждение"],\n'
            '  "overall_confidence": 0.0,\n'
            '  "recommendation": "auto_publish|needs_review|blocked",\n'
            '  "explanation": "краткое итоговое объяснение"\n'
            "}\n\n"
            "Строгие правила source_type:\n"
            "- используй только значения: input_text, ocr, qr, url, search, database, media_search, manual, unknown;\n"
            "- не используй url_read, url_parser, groq_search, web_search как source_type;\n"
            "- если факт получен из результата url_read, source_type должен быть url;\n"
            "- если факт получен из поиска, source_type должен быть search.\n\n"
            "Строгие правила missing_fields:\n"
            "- missing_fields  это только поля, которых вообще нет;\n"
            "- если дата есть, но не подтверждена, НЕ добавляй date/дата в missing_fields;\n"
            "- если город есть, но не подтверждён, НЕ добавляй city/город в missing_fields;\n"
            "- если площадка есть, но конфликтует или не подтверждена, НЕ добавляй venue/площадка в missing_fields;\n"
            "- неподтверждённые поля отражай через facts.status=unverified и warnings;\n"
            "- конфликтующие поля отражай через facts.status=conflicted и conflicts.\n\n"
            "Правила проверки:\n"
            "- не выдумывай даты, площадки, адреса, цены и ссылки;\n- если во входных данных дата без года, не додумывай год и не превращай её в YYYY-MM-DD; оставь исходную дату, например 20 августа;\n"
            "- search даёт только candidate/unverified, пока факт не подтверждён URL/БД/manual;\n"
            "- url может подтверждать источник только если страница успешно прочитана, не заблокирована антиботом и содержит нужный факт;\n"
            "- данные из исходного текста имеют status=input, но это не то же самое, что verified;\n"
            "- если есть конфликт даты, города, площадки или ссылки, recommendation не может быть auto_publish;\n"
            "- если нет даты или города вообще, recommendation должен быть blocked или needs_review;\n"
            "- если дата/город есть, но они не подтверждены, recommendation обычно needs_review;\n"
            "- если уверенность высокая и обязательные поля подтверждены, можно ставить auto_publish;\n"
            "- confidence всегда число от 0.0 до 1.0.\n\n"
            "Задача агента:\n"
            f"{goal.strip()}\n\n"
            "Результаты инструментов:\n"
            f"{self._format_tool_outputs(tool_outputs)}\n\n"
            "Evidence:\n"
            f"{json.dumps(evidence_set.to_dict(), ensure_ascii=False, indent=2, default=str)}"
        )

    def _format_tool_outputs(
        self,
        tool_outputs: list[AgentToolOutput],
    ) -> str:
        if not tool_outputs:
            return "Инструменты не вызывались."

        return json.dumps(
            [
                {
                    "tool_name": output.tool_name,
                    "ok": output.ok,
                    "data": output.data,
                    "error": output.error,
                    "metadata": output.metadata,
                }
                for output in tool_outputs
            ],
            ensure_ascii=False,
            indent=2,
            default=str,
        )
