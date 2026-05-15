import os

from app.application.ai_debug import AIVisualDebugSink
from app.application.contracts import AIProvider, AIProviderRoutingConfig
from app.application.provider_router import AIProviderRouter
from app.infrastructure.env import load_env_file
from app.infrastructure.providers.content_mock import ContentMockAIProvider
from app.infrastructure.providers.groq import (
    GroqProvider,
    GroqSearchProvider,
    GroqVisionProvider,
    load_groq_provider_config,
)
from app.infrastructure.providers.mira import (
    MiraTelegramProvider,
    load_mira_telegram_config,
)
from app.infrastructure.providers.mock import MockAIProvider


DEFAULT_PROVIDER_NAMES = [
    "groq",
    "groq_search",
    "groq_vision",
    "mira_telegram",
    "content_mock",
    "mock",
]


def load_enabled_provider_names() -> list[str]:
    load_env_file()

    raw_value = os.getenv("AI_PROVIDER_NAMES")

    if not raw_value:
        return DEFAULT_PROVIDER_NAMES.copy()

    provider_names = [
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    ]

    if provider_names:
        return provider_names

    return DEFAULT_PROVIDER_NAMES.copy()


def build_ai_provider(name: str) -> AIProvider:
    load_env_file()

    normalized_name = name.strip().lower().replace("-", "_")

    if normalized_name == "mock":
        return MockAIProvider()

    if normalized_name == "content_mock":
        return ContentMockAIProvider()

    if normalized_name == "groq":
        return GroqProvider(
            config=load_groq_provider_config(),
        )

    if normalized_name in {"groq_search", "search"}:
        return GroqSearchProvider(
            config=load_groq_provider_config(),
        )

    if normalized_name in {"groq_vision", "groq-vision", "vision"}:
        return GroqVisionProvider(
            config=load_groq_provider_config(),
        )

    if normalized_name in {"mira", "mira_telegram"}:
        return MiraTelegramProvider(
            config=load_mira_telegram_config(),
        )

    raise ValueError(f"Unknown AI provider: {name}")


def build_ai_providers(
    provider_names: list[str] | None = None,
) -> list[AIProvider]:
    names = provider_names or load_enabled_provider_names()

    providers: list[AIProvider] = []

    for name in names:
        provider = build_ai_provider(name)

        if provider.name in {item.name for item in providers}:
            continue

        providers.append(provider)

    if not providers:
        raise ValueError("No AI providers were built")

    return providers


def build_provider_router(
    provider_names: list[str] | None = None,
    routing_config: AIProviderRoutingConfig | None = None,
    debug_sink: AIVisualDebugSink | None = None,
) -> AIProviderRouter:
    return AIProviderRouter(
        providers=build_ai_providers(provider_names),
        routing_config=routing_config or load_provider_routing_config(),
        debug_sink=debug_sink,
    )


def load_provider_routing_config() -> AIProviderRoutingConfig:
    load_env_file()

    return AIProviderRoutingConfig(
        enable_fallback=_read_bool(
            "AI_PROVIDER_ENABLE_FALLBACK",
            True,
        ),
        stream_fallback_to_generate=_read_bool(
            "AI_PROVIDER_STREAM_FALLBACK_TO_GENERATE",
            True,
        ),
    )


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

