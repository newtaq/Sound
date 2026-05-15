import os

from app.infrastructure.env_loader import load_project_env
from dataclasses import dataclass


@dataclass(slots=True)
class AIProviderConfig:
    name: str
    enabled: bool
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 1


def _env_name(provider_name: str, key: str) -> str:
    normalized_provider = provider_name.upper().replace("-", "_")
    return f"AI_PROVIDER_{normalized_provider}_{key}"


def _read_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def _read_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def load_provider_config(provider_name: str) -> AIProviderConfig:
    load_project_env()
    return AIProviderConfig(
        name=provider_name,
        enabled=_read_bool(_env_name(provider_name, "ENABLED"), default=False),
        api_key=os.getenv(_env_name(provider_name, "API_KEY")),
        base_url=os.getenv(_env_name(provider_name, "BASE_URL")),
        model=os.getenv(_env_name(provider_name, "MODEL")),
        timeout_seconds=_read_float(
            _env_name(provider_name, "TIMEOUT_SECONDS"),
            default=60.0,
        ),
        max_retries=_read_int(
            _env_name(provider_name, "MAX_RETRIES"),
            default=1,
        ),
    )


def load_provider_configs(provider_names: list[str]) -> list[AIProviderConfig]:
    load_project_env()
    return [
        load_provider_config(provider_name)
        for provider_name in provider_names
    ]
    

