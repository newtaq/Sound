import os

from app.infrastructure.env_loader import load_project_env
from dataclasses import dataclass


@dataclass(slots=True)
class TelegramVisualDebugConfig:
    enabled: bool = False

    bot_token: str | None = None
    chat_id: int | str | None = None

    create_topics_enabled: bool = True
    topic_store_path: str = ".runtime/telegram_debug_topics.json"
    topic_name_prefix: str = "AI"

    max_topic_name_length: int = 128
    max_message_length: int = 3500
    send_timeout_seconds: float = 5.0

    include_request_text: bool = True
    include_response_text: bool = True
    include_metadata: bool = True
    include_stream_deltas: bool = False

    fail_silently: bool = True


def load_telegram_visual_debug_config() -> TelegramVisualDebugConfig:
    load_project_env()
    return TelegramVisualDebugConfig(
        enabled=_read_bool("AI_TELEGRAM_DEBUG_ENABLED", False),
        bot_token=os.getenv("AI_TELEGRAM_DEBUG_BOT_TOKEN") or None,
        chat_id=_read_chat_id("AI_TELEGRAM_DEBUG_CHAT_ID"),
        create_topics_enabled=_read_bool(
            "AI_TELEGRAM_DEBUG_CREATE_TOPICS_ENABLED",
            True,
        ),
        topic_store_path=os.getenv(
            "AI_TELEGRAM_DEBUG_TOPIC_STORE_PATH",
            ".runtime/telegram_debug_topics.json",
        ),
        topic_name_prefix=os.getenv(
            "AI_TELEGRAM_DEBUG_TOPIC_NAME_PREFIX",
            "AI",
        ),
        max_topic_name_length=_read_int(
            "AI_TELEGRAM_DEBUG_MAX_TOPIC_NAME_LENGTH",
            128,
        ),
        max_message_length=_read_int(
            "AI_TELEGRAM_DEBUG_MAX_MESSAGE_LENGTH",
            3500,
        ),
        send_timeout_seconds=_read_float(
            "AI_TELEGRAM_DEBUG_SEND_TIMEOUT_SECONDS",
            5.0,
        ),
        include_request_text=_read_bool(
            "AI_TELEGRAM_DEBUG_INCLUDE_REQUEST_TEXT",
            True,
        ),
        include_response_text=_read_bool(
            "AI_TELEGRAM_DEBUG_INCLUDE_RESPONSE_TEXT",
            True,
        ),
        include_metadata=_read_bool(
            "AI_TELEGRAM_DEBUG_INCLUDE_METADATA",
            True,
        ),
        include_stream_deltas=_read_bool(
            "AI_TELEGRAM_DEBUG_INCLUDE_STREAM_DELTAS",
            False,
        ),
        fail_silently=_read_bool(
            "AI_TELEGRAM_DEBUG_FAIL_SILENTLY",
            True,
        ),
    )


def _read_bool(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "y", "on"}:
        return True

    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    return default


def _read_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value.strip())
    except ValueError:
        return default


def _read_float(
    name: str,
    default: float,
) -> float:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return float(value.strip())
    except ValueError:
        return default


def _read_chat_id(
    name: str,
) -> int | str | None:
    value = os.getenv(name)

    if value is None:
        return None

    normalized = value.strip()

    if not normalized:
        return None

    try:
        return int(normalized)
    except ValueError:
        return normalized
