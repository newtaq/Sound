import asyncio
import json

from app.application.agent_core.tools import AgentToolInput
from app.infrastructure import build_ai_client
from app.infrastructure.agent_tools import GroqSearchAgentTool


async def main() -> None:
    ai_client = build_ai_client()
    tool = GroqSearchAgentTool(ai_client)

    result = await tool.run(
        AgentToolInput(
            tool_name="groq_search",
            arguments={
                "query": (
                    "Найди актуальную информацию: какая последняя стабильная "
                    "версия Python сейчас? Укажи версию, дату релиза и источник."
                ),
                "context": "Это smoke-test инструмента интернет-поиска для AI agent.",
            },
            metadata={
                "test_name": "groq_search_tool_smoke_test",
            },
        )
    )

    print("TOOL:", result.tool_name)
    print("OK:", result.ok)
    print("ERROR:", result.error)

    print("\nDATA:")
    print(
        json.dumps(
            result.data,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print("\nMETADATA:")
    print(
        json.dumps(
            result.metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    if not result.ok:
        raise SystemExit(1)

    if not result.data or not str(result.data.get("text", "")).strip():
        raise SystemExit(1)

    print("\nok")


if __name__ == "__main__":
    asyncio.run(main())
    

