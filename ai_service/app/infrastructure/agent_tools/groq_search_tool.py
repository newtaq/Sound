from typing import Any

from app.application.agent_core.tool_enums import (
    AgentToolCategory,
    AgentToolCostLevel,
    AgentToolTrustLevel,
)
from app.application.agent_core.tools import (
    AgentToolInput,
    AgentToolOutput,
    AgentToolSpec,
)
from app.application.ai_client import AIClient


class GroqSearchAgentTool:
    def __init__(
        self,
        ai_client: AIClient,
    ) -> None:
        self._ai_client = ai_client

    @property
    def spec(
        self,
    ) -> AgentToolSpec:
        return AgentToolSpec(
            name="groq_search",
            description=(
                "Ищет актуальную информацию в интернете через Groq Search. "
                "Используй этот инструмент, когда нужно найти кандидаты источников: "
                "официальные страницы мероприятий, артистов, площадки, даты, "
                "билетные страницы или свежие внешние подтверждения. "
                "Важно: результат поиска сам по себе не является verified-фактом."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Что нужно найти или проверить.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Дополнительный контекст задачи.",
                    },
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "provider_name": {
                        "type": "string",
                    },
                    "request_id": {
                        "type": "string",
                    },
                },
            },
            category=AgentToolCategory.SEARCH,
            capabilities=[
                "find_sources",
                "find_event_info",
                "find_artist_info",
                "find_venue_info",
                "find_ticket_pages",
                "find_official_pages",
            ],
            produces_evidence=True,
            trust_level=AgentToolTrustLevel.CANDIDATE,
            cost_level=AgentToolCostLevel.MEDIUM,
            can_run_automatically=False,
            can_be_called_by_agent=True,
            timeout_seconds=45.0,
        )

    async def run(
        self,
        tool_input: AgentToolInput,
    ) -> AgentToolOutput:
        query = self._read_string(
            tool_input.arguments,
            "query",
        )
        context = self._read_string(
            tool_input.arguments,
            "context",
        )

        if not query:
            return AgentToolOutput(
                tool_name=self.spec.name,
                ok=False,
                error="Argument 'query' is required",
            )

        response = await self._ai_client.ask(
            text=self._build_prompt(
                query=query,
                context=context,
            ),
            provider_name="groq_search",
            instructions=(
                "Используй интернет-поиск, если он доступен. "
                "Не выдумывай факты. Если точных данных нет, так и скажи. "
                "По возможности указывай найденные ссылки или названия источников. "
                "Помни: результат поиска — это кандидат, а не финальное подтверждение."
            ),
            response_format="plain_text",
            use_history=False,
            save_history=False,
            metadata={
                **tool_input.metadata,
                "agent_tool": self.spec.name,
            },
        )

        if response.error:
            return AgentToolOutput(
                tool_name=self.spec.name,
                ok=False,
                error=response.error,
                metadata={
                    "response_status": response.status.value,
                    "provider_name": response.provider_name,
                    "request_id": response.request_id,
                    "response_metadata": response.metadata,
                },
            )

        return AgentToolOutput(
            tool_name=self.spec.name,
            ok=True,
            data={
                "text": response.text,
                "provider_name": response.provider_name,
                "request_id": response.request_id,
            },
            metadata={
                "response_status": response.status.value,
                "response_metadata": response.metadata,
            },
        )

    def _build_prompt(
        self,
        query: str,
        context: str,
    ) -> str:
        return query.strip()

    def _read_string(
        self,
        data: dict[str, Any],
        key: str,
    ) -> str:
        value = data.get(key)

        if not isinstance(value, str):
            return ""

        return value.strip()
    



