import asyncio
import json

from app.application.contracts import AIMode
from app.application.poster_agent.pipeline import PosterAgentPipelineRequest
from app.infrastructure.service_factory import build_poster_agent_pipeline


TEST_INPUT = """
КИШЛАК

12 мая — Санкт-Петербург
Клуб Sound

Билеты: https://example.com
"""


async def main() -> None:
    pipeline = build_poster_agent_pipeline()

    result = await pipeline.run(
        PosterAgentPipelineRequest(
            input_text=TEST_INPUT,
            mode=AIMode.DEEP,
            max_steps=6,
            use_search=True,
            use_url_read=True,
            adaptive_tools=True,
            verify_urls=[
                "https://example.com",
            ],
            metadata={
                "script": "test_poster_agent_pipeline",
            },
        )
    )

    print("\n=== REVIEW TEXT ===")
    print(result.review_text)

    print("\n=== STRUCTURED RESULT ===")
    print(
        json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    print("\n=== AGENT STEPS ===")
    for step in result.agent_run.steps:
        print(f"{step.index}. {step.step_type.value}: {step.content}")


if __name__ == "__main__":
    asyncio.run(main())
    
