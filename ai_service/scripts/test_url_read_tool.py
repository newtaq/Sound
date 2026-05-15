import asyncio
import json

from app.application.agent_core.tools import AgentToolInput
from app.infrastructure.agent_tools import UrlReadAgentTool


async def main() -> None:
    tool = UrlReadAgentTool(
        timeout_seconds=20,
        text_preview_limit=2000,
    )

    result = await tool.run(
        AgentToolInput(
            tool_name="url_read",
            arguments={
                "urls": [
                    "https://msk.kassir.ru/koncert/kishlak",
                    "https://spb.kassir.ru/koncert/kishlak-7",
                    "https://kishlak-concert.ru/",
                ],
            },
            metadata={
                "test_name": "url_read_tool_smoke_test",
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


if __name__ == "__main__":
    asyncio.run(main())
    

