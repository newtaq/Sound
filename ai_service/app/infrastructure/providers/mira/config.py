import os

from app.infrastructure.env_loader import load_project_env
from dataclasses import dataclass

from app.infrastructure.env import load_env_file


@dataclass(slots=True)
class MiraTelegramProxyConfig:
    scheme: str
    hostname: str
    port: int
    username: str | None = None
    password: str | None = None

    def to_pyrogram_proxy(self) -> dict:
        proxy = {
            "scheme": self.scheme,
            "hostname": self.hostname,
            "port": self.port,
        }

        if self.username:
            proxy["username"] = self.username

        if self.password:
            proxy["password"] = self.password

        return proxy


@dataclass(slots=True)
class MiraTelegramProviderConfig:
    api_id: int | None = None
    api_hash: str | None = None

    session_name: str = "mira_telegram"
    session_string: str | None = None

    bot_username: str = "mira"
    bot_token: str | None = None

    chat_id: str | int | None = None
    stream_chat_id: str | int | None = None

    forum_topics_enabled: bool = True
    topic_store_path: str = ".runtime/mira_topics.json"
    topic_name_prefix: str = "AI session"

    trigger_prefix: str = "мира"

    request_timeout_seconds: float = 120.0
    idle_timeout_seconds: float = 3.0

    max_text_message_length: int = 4096
    max_caption_length: int = 1024
    max_media_count: int = 10

    max_retries: int = 1
    retry_delay_seconds: float = 1.0

    one_active_request_per_session: bool = True
    send_large_text_as_file: bool = True
    allow_media_group: bool = True

    proxy: MiraTelegramProxyConfig | None = None


def load_mira_telegram_config() -> MiraTelegramProviderConfig:
    load_project_env()
    load_env_file()

    return MiraTelegramProviderConfig(
        api_id=_read_int("AI_PROVIDER_MIRA_TELEGRAM_API_ID"),
        api_hash=os.getenv("AI_PROVIDER_MIRA_TELEGRAM_API_HASH"),
        session_name=os.getenv(
            "AI_PROVIDER_MIRA_TELEGRAM_SESSION_NAME",
            "mira_telegram",
        ),
        session_string=os.getenv("AI_PROVIDER_MIRA_TELEGRAM_SESSION_STRING"),
        bot_username=os.getenv(
            "AI_PROVIDER_MIRA_TELEGRAM_BOT_USERNAME",
            "mira",
        ),
        bot_token=os.getenv("AI_PROVIDER_MIRA_TELEGRAM_BOT_TOKEN"),
        chat_id=_read_chat_id("AI_PROVIDER_MIRA_TELEGRAM_CHAT_ID"),
        stream_chat_id=_read_chat_id("AI_PROVIDER_MIRA_TELEGRAM_STREAM_CHAT_ID"),
        forum_topics_enabled=_read_bool(
            "AI_PROVIDER_MIRA_TELEGRAM_FORUM_TOPICS_ENABLED",
            True,
        ),
        topic_store_path=os.getenv(
            "AI_PROVIDER_MIRA_TELEGRAM_TOPIC_STORE_PATH",
            ".runtime/mira_topics.json",
        ),
        topic_name_prefix=os.getenv(
            "AI_PROVIDER_MIRA_TELEGRAM_TOPIC_NAME_PREFIX",
            "AI session",
        ),
        trigger_prefix=os.getenv(
            "AI_PROVIDER_MIRA_TELEGRAM_TRIGGER_PREFIX",
            "мира",
        ),
        request_timeout_seconds=_read_float(
            "AI_PROVIDER_MIRA_TELEGRAM_TIMEOUT_SECONDS",
            120.0,
        ),
        idle_timeout_seconds=_read_float(
            "AI_PROVIDER_MIRA_TELEGRAM_IDLE_TIMEOUT_SECONDS",
            3.0,
        ),
        max_text_message_length=_read_int(
            "AI_PROVIDER_MIRA_TELEGRAM_MAX_TEXT_MESSAGE_LENGTH",
            4096,
        ) or 4096,
        max_caption_length=_read_int(
            "AI_PROVIDER_MIRA_TELEGRAM_MAX_CAPTION_LENGTH",
            1024,
        ) or 1024,
        max_media_count=_read_int(
            "AI_PROVIDER_MIRA_TELEGRAM_MAX_MEDIA_COUNT",
            10,
        ) or 10,
        max_retries=_read_int(
            "AI_PROVIDER_MIRA_TELEGRAM_MAX_RETRIES",
            1,
        ) or 1,
        retry_delay_seconds=_read_float(
            "AI_PROVIDER_MIRA_TELEGRAM_RETRY_DELAY_SECONDS",
            1.0,
        ),
        one_active_request_per_session=_read_bool(
            "AI_PROVIDER_MIRA_TELEGRAM_ONE_ACTIVE_REQUEST_PER_SESSION",
            True,
        ),
        send_large_text_as_file=_read_bool(
            "AI_PROVIDER_MIRA_TELEGRAM_SEND_LARGE_TEXT_AS_FILE",
            True,
        ),
        allow_media_group=_read_bool(
            "AI_PROVIDER_MIRA_TELEGRAM_ALLOW_MEDIA_GROUP",
            True,
        ),
        proxy=_read_proxy_config(),
    )


def _read_proxy_config() -> MiraTelegramProxyConfig | None:
    hostname = os.getenv("AI_PROVIDER_MIRA_TELEGRAM_PROXY_HOSTNAME")
    port = _read_int("AI_PROVIDER_MIRA_TELEGRAM_PROXY_PORT")

    if not hostname or port is None:
        return None

    return MiraTelegramProxyConfig(
        scheme=os.getenv(
            "AI_PROVIDER_MIRA_TELEGRAM_PROXY_SCHEME",
            "socks5",
        ),
        hostname=hostname,
        port=port,
        username=os.getenv("AI_PROVIDER_MIRA_TELEGRAM_PROXY_USERNAME") or None,
        password=os.getenv("AI_PROVIDER_MIRA_TELEGRAM_PROXY_PASSWORD") or None,
    )


def _read_bool(name: str, default: bool) -> bool:
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


def _read_int(name: str, default: int | None = None) -> int | None:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _read_chat_id(name: str) -> str | int | None:
    value = os.getenv(name)
    if value is None:
        return None

    value = value.strip()
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return value
    

