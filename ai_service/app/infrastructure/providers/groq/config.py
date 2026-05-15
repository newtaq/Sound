import os

from app.infrastructure.env_loader import load_project_env
from dataclasses import dataclass, field

from app.infrastructure.env import load_env_file


@dataclass(slots=True)
class GroqProviderConfig:
    api_keys: list[str] = field(default_factory=list)

    model: str = "llama-3.3-70b-versatile"
    search_model: str = "groq/compound-mini"
    vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    temperature: float = 0.2
    max_completion_tokens: int = 4096
    timeout_seconds: float = 60.0
    max_retries: int = 1
    retry_delay_seconds: float = 1.0

    key_strategy: str = "round_robin"

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_keys)

    def get_all_api_keys(self) -> list[str]:
        return self.api_keys.copy()


def load_groq_provider_config() -> GroqProviderConfig:
    load_project_env()
    load_env_file()

    return GroqProviderConfig(
        api_keys=_read_list("GROQ_API_KEYS"),
        model=os.getenv(
            "AI_PROVIDER_GROQ_MODEL",
            "llama-3.3-70b-versatile",
        ),
        search_model=os.getenv(
            "AI_PROVIDER_GROQ_SEARCH_MODEL",
            "groq/compound-mini",
        ),
        vision_model=os.getenv(
            "AI_PROVIDER_GROQ_VISION_MODEL",
            "meta-llama/llama-4-scout-17b-16e-instruct",
        ),
        temperature=_read_float(
            "AI_PROVIDER_GROQ_TEMPERATURE",
            0.2,
        ),
        max_completion_tokens=_read_int(
            "AI_PROVIDER_GROQ_MAX_COMPLETION_TOKENS",
            4096,
        ) or 4096,
        timeout_seconds=_read_float(
            "AI_PROVIDER_GROQ_TIMEOUT_SECONDS",
            60.0,
        ),
        max_retries=_read_int(
            "AI_PROVIDER_GROQ_MAX_RETRIES",
            1,
        ) or 1,
        retry_delay_seconds=_read_float(
            "AI_PROVIDER_GROQ_RETRY_DELAY_SECONDS",
            1.0,
        ),
        key_strategy=os.getenv(
            "AI_PROVIDER_GROQ_KEY_STRATEGY",
            "round_robin",
        ),
    )


def _read_list(
    name: str,
) -> list[str]:
    value = os.getenv(name)

    if value is None:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def _read_float(
    name: str,
    default: float,
) -> float:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def _read_int(
    name: str,
    default: int | None = None,
) -> int | None:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default
    

