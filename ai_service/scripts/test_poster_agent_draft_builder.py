import asyncio
import json

from app.application.agent_core.runner import AgentRunRequest, AgentRunner
from app.application.agent_core.tools import AgentToolInput, AgentToolRegistry
from app.application.poster_agent.draft_builder import (
    PosterAgentDraftBuildRequest,
    PosterAgentDraftBuilder,
)
from app.application.poster_agent.draft_validator import PosterAgentDraftValidator
from app.application.poster_agent.renderer import PosterAgentRenderer
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
                "test_name": "poster_agent_draft_builder_smoke_test",
            },
        )
    )

    builder = PosterAgentDraftBuilder()
    draft = builder.build(
        PosterAgentDraftBuildRequest(
            agent_run=run,
        )
    )

    validator = PosterAgentDraftValidator()
    decision = validator.validate(draft)

    renderer = PosterAgentRenderer()
    review_text = renderer.render_review_text(
        draft=draft,
        decision=decision,
    )

    print("AGENT STATUS:", run.status.value)
    print("AGENT REQUEST:", run.request_id)
    print("EVIDENCE COUNT:", len(run.evidence.items))
    print("VERIFIED EVIDENCE:", len(run.evidence.verified_items()))
    print("UNVERIFIED EVIDENCE:", len(run.evidence.unverified_items()))

    print("\nPUBLISH DECISION:")
    print(
        json.dumps(
            decision.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print("\nREVIEW TEXT:")
    print(review_text)

    print("\nDRAFT:")
    print(
        json.dumps(
            draft.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
    





