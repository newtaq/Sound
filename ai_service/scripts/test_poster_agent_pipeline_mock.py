import asyncio
import json

from app.application.contracts import AIMode
from app.application.poster_agent import PosterAgentPipelineRequest
from app.infrastructure.service_factory import build_poster_agent_pipeline


TEST_INPUT = """
КИШЛАК

12 мая  Санкт-Петербург
Клуб Sound

Билеты: https://example.com
"""


async def main() -> None:
    pipeline = build_poster_agent_pipeline(
        provider_names=["mock"],
    )

    result = await pipeline.run(
        PosterAgentPipelineRequest(
            input_text=TEST_INPUT,
            mode=AIMode.STANDARD,
            max_steps=4,
            use_search=False,
            use_url_read=False,
            adaptive_tools=False,
            structured_verification=False,
            metadata={
                "script": "test_poster_agent_pipeline_mock",
            },
        )
    )

    print("=== REVIEW TEXT ===")
    print(result.review_text)

    print("\n=== RESULT ===")
    print(
        json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    assert result.agent_run.final_result is not None
    assert result.verification_result is None
    assert result.verification_error is None

    print("\nok")


if __name__ == "__main__":
    asyncio.run(main())
