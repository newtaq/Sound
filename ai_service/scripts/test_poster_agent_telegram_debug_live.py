import asyncio
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from app.application.contracts import AIMedia, AIMediaType, AIMode
from app.application.poster_agent.pipeline import PosterAgentPipelineRequest
from app.infrastructure import (
    build_poster_agent_pipeline,
    flush_telegram_visual_debug_sink,
)


POSTER_PATH = Path("scripts/test_data/pepel_nahudi_poster.jpg")

SESSION_ID = "poster-agent-telegram-debug-pepel-nahudi-full-live-test"

TICKET_URL = "https://clck.ru/3THNTP"
SOCIAL_URL = "https://t.me/+pDVpAvK4hBZlNzAy"
OFFICIAL_URL = "https://red-summer.ru"

INPUT_TEXT = """
PEPEL NAHUDI

Pepel Nahudi впервые выходит на открытую летнюю сцену с большим сольным концертом в Санкт-Петербурге — без клаб-шоу и коллабораций, один на один со своей музыкой и аудиторией. Гостей ждёт самостоятельное, цельное высказывание с продуманной драматургией и загадочной энергетикой.

▫️Когда: 20 августа
▫️Где: Муз Порт
▫️Цена: от 2300 ₽
▫️Билеты: https://clck.ru/3THNTP

➡️ Концерты в Питере (https://t.me/+pDVpAvK4hBZlNzAy)
""".strip()


def main_print(title: str, value: Any = None) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    if value is not None:
        print_json(value)


def print_json(value: Any) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=json_default,
        )
    )


def json_default(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()

    if hasattr(value, "value"):
        return value.value

    if is_dataclass(value):
        return asdict(value)

    if isinstance(value, Path):
        return str(value)

    return str(value)


def to_dict_safe(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return data if isinstance(data, dict) else {}

    if is_dataclass(value):
        data = asdict(value)
        return data if isinstance(data, dict) else {}

    if isinstance(value, dict):
        return value

    return {}


def read_structured_data(result: Any) -> dict[str, Any]:
    final_result = getattr(result.agent_run, "final_result", None)

    if final_result is None:
        return {}

    structured_data = getattr(final_result, "structured_data", None)

    if isinstance(structured_data, dict):
        return structured_data

    return {}


def read_tool_results(result: Any) -> list[Any]:
    direct_tool_outputs = getattr(result.agent_run, "tool_outputs", None)

    if isinstance(direct_tool_outputs, list) and direct_tool_outputs:
        return direct_tool_outputs

    structured_data = read_structured_data(result)
    tool_results = structured_data.get("tool_results")

    if isinstance(tool_results, list):
        return tool_results

    return []


def read_verification_dict(result: Any) -> dict[str, Any]:
    if result.verification_result is not None:
        return to_dict_safe(result.verification_result)

    structured_data = read_structured_data(result)

    for key in ("poster_verification", "poster_verification_result"):
        value = structured_data.get(key)

        if isinstance(value, dict):
            return value

    return {}


def print_tool_results(result: Any) -> None:
    tool_results = read_tool_results(result)

    main_print(
        "TOOL RESULTS SUMMARY",
        {
            "tool_result_count": len(tool_results),
            "note": "Если здесь 0, значит агент не вызвал инструменты или они не попали в structured_data.",
        },
    )

    for index, item in enumerate(tool_results, start=1):
        main_print(f"TOOL RESULT #{index}", to_dict_safe(item) or item)


def print_links_from_verification(result: Any) -> None:
    verification = read_verification_dict(result)
    links = verification.get("links")

    if not isinstance(links, list):
        main_print("VERIFICATION LINKS", {"links": []})
        return

    short_links = []

    for item in links:
        if not isinstance(item, dict):
            continue

        short_links.append(
            {
                "url": item.get("url"),
                "kind": item.get("kind"),
                "title": item.get("title"),
                "verified": item.get("verified"),
                "confidence": item.get("confidence"),
                "source_type": item.get("source_type"),
                "explanation": item.get("explanation"),
            }
        )

    main_print("VERIFICATION LINKS", short_links)


def print_occurrences_from_verification(result: Any) -> None:
    verification = read_verification_dict(result)
    occurrences = verification.get("occurrences")

    if not isinstance(occurrences, list):
        main_print("VERIFICATION OCCURRENCES", {"occurrences": []})
        return

    main_print("VERIFICATION OCCURRENCES", occurrences)


def build_request() -> PosterAgentPipelineRequest:
    return PosterAgentPipelineRequest(
        input_text=INPUT_TEXT,
        session_id=SESSION_ID,
        provider_name="groq_vision",
        mode=AIMode.FAST,
        max_steps=8,
        use_search=True,
        use_url_read=True,
        adaptive_tools=True,
        structured_verification=True,
        search_query=(
            "PEPEL NAHUDI 20 августа Санкт-Петербург Муз Порт "
            "билеты официальный источник red-summer clck.ru"
        ),
        search_context=(
            "Live-тест poster-agent. Нужно проверить афишу концерта: "
            "артист, дата, город, площадка, билетная ссылка, официальный источник. "
            "Не выдумывать данные. Search даёт кандидатов, URL подтверждает только если "
            "страница успешно прочитана и содержит нужный факт."
        ),
        verify_urls=[
            TICKET_URL,
            OFFICIAL_URL,
            SOCIAL_URL,
        ],
        media=[
            AIMedia(
                media_type=AIMediaType.IMAGE,
                path=str(POSTER_PATH),
                mime_type="image/jpeg",
                filename=POSTER_PATH.name,
                metadata={
                    "source": "test_data",
                    "purpose": "poster_visual_verification",
                    "expected_contains": [
                        "PEPEL NAHUDI",
                        "20 августа",
                        "Санкт-Петербург",
                        "16+",
                        "red-summer.ru",
                    ],
                },
            )
        ],
        metadata={
            "test_name": "poster_agent_telegram_debug_live_pepel_nahudi_full",
            "event_title": "PEPEL NAHUDI",
            "event_date": "20 августа",
            "telegram_debug_photo_path": str(POSTER_PATH),
            "poster_path": str(POSTER_PATH),
            "expected_artist": "Pepel Nahudi",
            "expected_city": "Санкт-Петербург",
            "expected_venue": "Муз Порт",
            "expected_ticket_url": TICKET_URL,
            "expected_official_url": OFFICIAL_URL,
            "expected_social_url": SOCIAL_URL,
            "live_test": True,
            "live_test_goal": (
                "Показать полный цикл: картинка, поиск, чтение URL, verification, "
                "черновик, текст будущего поста и Telegram debug-сообщения."
            ),
        },
    )


async def main() -> None:
    if not POSTER_PATH.exists():
        raise FileNotFoundError(f"Poster image not found: {POSTER_PATH}")

    request = build_request()

    main_print(
        "LIVE TEST REQUEST",
        {
            "session_id": request.session_id,
            "provider_name": request.provider_name,
            "mode": request.mode.value,
            "max_steps": request.max_steps,
            "use_search": request.use_search,
            "use_url_read": request.use_url_read,
            "adaptive_tools": request.adaptive_tools,
            "structured_verification": request.structured_verification,
            "verify_urls": request.verify_urls,
            "media_count": len(request.media),
            "poster_path": str(POSTER_PATH),
        },
    )

    pipeline = build_poster_agent_pipeline(
        provider_names=[
            "groq_vision",
            "groq",
            "groq_search",
            "content_mock",
            "mock",
        ],
    )

    result = await pipeline.run(request)

    main_print(
        "BASIC RESULT",
        {
            "agent_status": result.agent_run.status.value,
            "session_id": result.agent_run.session_id,
            "draft_title": result.draft.title,
            "draft_status": result.draft.status.value,
            "decision_status": result.decision.status.value,
            "can_publish": result.decision.can_publish,
            "verification_error": result.verification_error,
        },
    )

    main_print("AGENT METADATA", result.agent_run.metadata)

    post_text = result.agent_run.metadata.get("poster_agent_post_text")

    main_print(
        "POST TEXT",
        {
            "exists": isinstance(post_text, str) and bool(post_text.strip()),
            "text": post_text,
        },
    )

    main_print("REVIEW TEXT", {"text": result.review_text})

    if result.verification_result is not None:
        main_print("VERIFICATION RESULT", result.verification_result)

    print_occurrences_from_verification(result)
    print_links_from_verification(result)
    print_tool_results(result)

    main_print("FULL RESULT DICT", result.to_dict())

    print()
    print("flushing telegram debug background tasks...")
    await flush_telegram_visual_debug_sink()

    metadata = result.agent_run.metadata
    tool_results = read_tool_results(result)

    assert result.agent_run.status.value == "finished"
    assert result.draft.title
    assert metadata.get("poster_agent_pipeline") is True
    assert metadata.get("use_search") is True
    assert metadata.get("use_url_read") is True
    assert metadata.get("adaptive_tools") is True
    assert metadata.get("media_count") == 1
    assert metadata.get("total_verify_url_count", 0) >= 3
    assert isinstance(metadata.get("poster_agent_post_text"), str)
    assert metadata["poster_agent_post_text"].strip()

    if not tool_results:
        print()
        print("WARNING: tool_results is empty.")
        print("Это не всегда значит, что тест сломан, но для полноценного live-теста нужно проверить AgentRunner/tool storage.")

    print()
    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
    