import os

from app.infrastructure.providers import load_provider_config


def main() -> None:
    os.environ["AI_PROVIDER_TEST_ENABLED"] = "true"
    os.environ["AI_PROVIDER_TEST_API_KEY"] = "test-key"
    os.environ["AI_PROVIDER_TEST_BASE_URL"] = "https://example.com/api"
    os.environ["AI_PROVIDER_TEST_MODEL"] = "test-model"
    os.environ["AI_PROVIDER_TEST_TIMEOUT_SECONDS"] = "12.5"
    os.environ["AI_PROVIDER_TEST_MAX_RETRIES"] = "3"

    config = load_provider_config("test")

    print("CONFIG:", config)
    print("NAME:", config.name)
    print("ENABLED:", config.enabled)
    print("API KEY:", config.api_key)
    print("BASE URL:", config.base_url)
    print("MODEL:", config.model)
    print("TIMEOUT:", config.timeout_seconds)
    print("MAX RETRIES:", config.max_retries)

    if config.name != "test":
        raise SystemExit("Invalid provider name")

    if not config.enabled:
        raise SystemExit("Provider must be enabled")

    if config.api_key != "test-key":
        raise SystemExit("Invalid API key")

    if config.base_url != "https://example.com/api":
        raise SystemExit("Invalid base URL")

    if config.model != "test-model":
        raise SystemExit("Invalid model")

    if config.timeout_seconds != 12.5:
        raise SystemExit("Invalid timeout")

    if config.max_retries != 3:
        raise SystemExit("Invalid max retries")


if __name__ == "__main__":
    main()
    
