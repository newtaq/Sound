from typing import Any

from app.infrastructure.env import load_env_file

__all__ = [
    "build_ai_client",
    "build_ai_service",
    "build_conversation_store",
    "build_poster_agent_pipeline",
    "load_env_file",
    "flush_telegram_visual_debug_sink",
]


def build_ai_client(*args: Any, **kwargs: Any) -> Any:
    from app.infrastructure.service_factory import build_ai_client as factory

    return factory(*args, **kwargs)


def build_ai_service(*args: Any, **kwargs: Any) -> Any:
    from app.infrastructure.service_factory import build_ai_service as factory

    return factory(*args, **kwargs)


def build_conversation_store(*args: Any, **kwargs: Any) -> Any:
    from app.infrastructure.conversation_store import build_conversation_store as factory

    return factory(*args, **kwargs)



def build_poster_agent_pipeline(*args: Any, **kwargs: Any) -> Any:
    from app.infrastructure.service_factory import (
        build_poster_agent_pipeline as factory,
    )

    return factory(*args, **kwargs)



async def flush_telegram_visual_debug_sink() -> None:
    from app.infrastructure.service_factory import (
        flush_telegram_visual_debug_sink as factory,
    )

    await factory()
