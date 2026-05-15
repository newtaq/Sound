import asyncio
import json

from app.application.agent_core.runner import AgentRunRequest, AgentRunner
from app.application.agent_core.tools import AgentToolInput, AgentToolRegistry
from app.infrastructure import build_ai_client
from app.infrastructure.agent_tools import GroqSearchAgentTool, UrlReadAgentTool


async def main() -> None:
    ai_client = build_ai_client()

    tool_registry = AgentToolRegistry(
        tools=[
            GroqSearchAgentTool(ai_client),
            UrlReadAgentTool(
                timeout_seconds=20,
                text_preview_limit=3000,
            ),
        ]
    )

    runner = AgentRunner(
        ai_client=ai_client,
        tool_registry=tool_registry,
    )

    run = await runner.run(
        AgentRunRequest(
            goal=(
                "Из этих данных собери черновик афиши:\n\n"
                "Кишлак. Тур 2026.\n"
                "12 мая — Москва\n"
                "14 мая — Санкт-Петербург\n"
                "Билеты скоро.\n\n"
                "Нужно вывести: тип события, артистов, города, даты, "
                "что известно точно из входных данных, что найдено через поиск, "
                "что удалось проверить прямым чтением URL, какие есть конфликты "
                "и чего не хватает для полной публикации."
            ),
            provider_name="groq",
            required_tools=[
                AgentToolInput(
                    tool_name="groq_search",
                    arguments={
                        "query": (
                            "Кишлак тур 2026 Москва 12 мая Санкт-Петербург "
                            "14 мая билеты площадка"
                        ),
                        "context": (
                            "Проверяем данные для черновика афиши. "
                            "Нужно найти только подтверждающую информацию: "
                            "официальные страницы, билеты, площадки, даты."
                        ),
                    },
                    metadata={
                        "purpose": "find_candidate_sources",
                    },
                ),
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
                        "purpose": "verify_candidate_sources",
                    },
                ),
            ],
            metadata={
                "test_name": "agent_runner_with_search_and_url_read_tools",
            },
        )
    )

    print("STATUS:", run.status.value)
    print("SESSION:", run.session_id)
    print("REQUEST:", run.request_id)
    print("GOAL:")
    print(run.goal)

    print("\nPLAN:")
    if run.plan is not None:
        print(
            json.dumps(
                {
                    "goal": run.plan.goal,
                    "steps": run.plan.steps,
                    "metadata": run.plan.metadata,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    print("\nSTEPS:")
    for step in run.steps:
        print("-" * 80)
        print("INDEX:", step.index)
        print("TYPE:", step.step_type.value)
        print("CONTENT:")
        print(step.content)

        if step.tool_call is not None:
            print("TOOL CALL:")
            print(
                json.dumps(
                    {
                        "tool_name": step.tool_call.tool_name,
                        "arguments": step.tool_call.arguments,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

        if step.tool_result is not None:
            print("TOOL RESULT:")
            print(
                json.dumps(
                    {
                        "tool_name": step.tool_result.tool_name,
                        "ok": step.tool_result.ok,
                        "data": step.tool_result.data,
                        "error": step.tool_result.error,
                        "metadata": step.tool_result.metadata,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

        if step.metadata:
            print("METADATA:")
            print(
                json.dumps(
                    step.metadata,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

    print("\nEVIDENCE:")
    print(
        json.dumps(
            run.evidence.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print("\nFINAL RESULT:")
    if run.final_result is not None:
        print(run.final_result.text)

        print("\nSTRUCTURED DATA:")
        print(
            json.dumps(
                run.final_result.structured_data,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        print("\nFINAL METADATA:")
        print(
            json.dumps(
                run.final_result.metadata,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    if run.error:
        print("\nERROR:")
        print(run.error)


if __name__ == "__main__":
    asyncio.run(main())
    


