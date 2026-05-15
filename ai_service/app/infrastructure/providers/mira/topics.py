import asyncio
import hashlib
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.application.contracts import AIMode
from app.infrastructure.providers.mira.config import MiraTelegramProviderConfig


DEFAULT_TOPIC_ICON_COLORS = [
    0x6FB9F0,
    0xFFD67E,
    0xCB86DB,
    0x8EEE98,
    0xFF93B2,
    0xFB6F5F,
]


@dataclass(slots=True)
class MiraTelegramTopicIcon:
    emoji: str | None
    custom_emoji_id: str


@dataclass(slots=True)
class MiraTelegramTopic:
    session_id: str
    chat_id: str | int
    message_thread_id: int
    name: str
    icon_custom_emoji_id: str | None = None
    request_count: int = 0
    mode: str = "ai"
    status: str = "active"
    short_session_id: str | None = None
    pinned_message_id: int | None = None
    last_request_id: str | None = None


class MiraTelegramTopicStore:
    async def get_topic(
        self,
        session_id: str,
    ) -> MiraTelegramTopic | None:
        raise NotImplementedError

    async def save_topic(
        self,
        topic: MiraTelegramTopic,
    ) -> None:
        raise NotImplementedError


class FileMiraTelegramTopicStore(MiraTelegramTopicStore):
    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()

    async def get_topic(
        self,
        session_id: str,
    ) -> MiraTelegramTopic | None:
        async with self._lock:
            data = self._read_data()

            item = data.get(session_id)
            if not isinstance(item, dict):
                return None

            message_thread_id = item.get("message_thread_id")
            name = item.get("name")
            chat_id = item.get("chat_id")
            icon_custom_emoji_id = item.get("icon_custom_emoji_id")
            request_count = item.get("request_count")
            mode = item.get("mode")
            status = item.get("status")
            short_session_id = item.get("short_session_id")
            pinned_message_id = item.get("pinned_message_id")
            last_request_id = item.get("last_request_id")

            if not isinstance(message_thread_id, int):
                return None

            if not isinstance(name, str):
                return None

            if not isinstance(chat_id, str | int):
                return None

            if icon_custom_emoji_id is not None and not isinstance(
                icon_custom_emoji_id,
                str,
            ):
                icon_custom_emoji_id = None

            if not isinstance(request_count, int):
                request_count = 0

            if not isinstance(mode, str):
                mode = "ai"

            if not isinstance(status, str):
                status = "active"

            if short_session_id is not None and not isinstance(short_session_id, str):
                short_session_id = None

            if pinned_message_id is not None and not isinstance(pinned_message_id, int):
                pinned_message_id = None

            if last_request_id is not None and not isinstance(last_request_id, str):
                last_request_id = None

            return MiraTelegramTopic(
                session_id=session_id,
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                name=name,
                icon_custom_emoji_id=icon_custom_emoji_id,
                request_count=request_count,
                mode=mode,
                status=status,
                short_session_id=short_session_id,
                pinned_message_id=pinned_message_id,
                last_request_id=last_request_id,
            )

    async def save_topic(
        self,
        topic: MiraTelegramTopic,
    ) -> None:
        async with self._lock:
            data = self._read_data()

            data[topic.session_id] = {
                "session_id": topic.session_id,
                "chat_id": topic.chat_id,
                "message_thread_id": topic.message_thread_id,
                "name": topic.name,
                "icon_custom_emoji_id": topic.icon_custom_emoji_id,
                "request_count": topic.request_count,
                "mode": topic.mode,
                "status": topic.status,
                "short_session_id": topic.short_session_id,
                "pinned_message_id": topic.pinned_message_id,
                "last_request_id": topic.last_request_id,
            }

            self._write_data(data)

    def _read_data(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(data, dict):
            return {}

        return data

    def _write_data(
        self,
        data: dict[str, Any],
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self._path.with_suffix(".tmp")

        temp_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temp_path.replace(self._path)


class MiraTelegramBotApiClient:
    def __init__(
        self,
        bot_token: str,
    ) -> None:
        self._bot_token = bot_token

    async def create_forum_topic(
        self,
        chat_id: str | int,
        name: str,
        icon_custom_emoji_id: str | None = None,
        icon_color: int | None = None,
    ) -> int:
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "name": name,
        }

        if icon_custom_emoji_id:
            data["icon_custom_emoji_id"] = icon_custom_emoji_id
        elif icon_color is not None:
            data["icon_color"] = icon_color

        response = await self._request(
            method="createForumTopic",
            data=data,
        )

        result = response.get("result")

        if not isinstance(result, dict):
            raise RuntimeError(
                f"Telegram Bot API returned invalid topic result: {response}"
            )

        message_thread_id = result.get("message_thread_id")

        if not isinstance(message_thread_id, int):
            raise RuntimeError(
                f"Telegram Bot API did not return message_thread_id: {response}"
            )

        return message_thread_id

    async def edit_forum_topic(
        self,
        chat_id: str | int,
        message_thread_id: int,
        name: str | None = None,
        icon_custom_emoji_id: str | None = None,
    ) -> None:
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }

        if name is not None:
            data["name"] = name

        if icon_custom_emoji_id is not None:
            data["icon_custom_emoji_id"] = icon_custom_emoji_id

        await self._request(
            method="editForumTopic",
            data=data,
        )

    async def delete_message(
        self,
        chat_id: str | int,
        message_id: int,
    ) -> None:
        await self._request(
            method="deleteMessage",
            data={
                "chat_id": chat_id,
                "message_id": message_id,
            },
        )

    async def get_forum_topic_icon_stickers(self) -> list[MiraTelegramTopicIcon]:
        response = await self._request(
            method="getForumTopicIconStickers",
            data={},
        )

        result = response.get("result")

        if not isinstance(result, list):
            return []

        icons: list[MiraTelegramTopicIcon] = []

        for item in result:
            if not isinstance(item, dict):
                continue

            custom_emoji_id = item.get("custom_emoji_id")
            emoji = item.get("emoji")

            if not isinstance(custom_emoji_id, str) or not custom_emoji_id:
                continue

            icons.append(
                MiraTelegramTopicIcon(
                    emoji=emoji if isinstance(emoji, str) else None,
                    custom_emoji_id=custom_emoji_id,
                )
            )

        return icons

    async def _request(
        self,
        method: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._request_sync,
            method,
            data,
        )

    def _request_sync(
        self,
        method: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self._bot_token}/{method}"

        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=encoded_data,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except Exception as exc:
            raise RuntimeError(
                f"Telegram Bot API request failed: {method}: {exc}"
            ) from exc

        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Telegram Bot API returned non-json response: {payload}"
            ) from exc

        if not isinstance(decoded, dict):
            raise RuntimeError(
                f"Telegram Bot API returned invalid response: {decoded}"
            )

        if decoded.get("ok") is not True:
            description = decoded.get("description") or decoded
            raise RuntimeError(
                f"Telegram Bot API error in {method}: {description}"
            )

        return decoded


class MiraTelegramTopicManager:
    def __init__(
        self,
        config: MiraTelegramProviderConfig,
        store: MiraTelegramTopicStore | None = None,
        bot_api_client: MiraTelegramBotApiClient | None = None,
    ) -> None:
        self._config = config
        self._store = store or FileMiraTelegramTopicStore(config.topic_store_path)
        self._bot_api_client = bot_api_client
        self._lock = asyncio.Lock()
        self._available_icons: list[MiraTelegramTopicIcon] | None = None

    async def get_message_thread_id(
        self,
        session_id: str | None,
    ) -> int | None:
        if session_id is None:
            return None

        if not self._config.forum_topics_enabled:
            return None

        async with self._lock:
            existing_topic = await self._store.get_topic(session_id)
            if existing_topic is not None:
                return existing_topic.message_thread_id

            topic = await self._create_topic(
                session_id=session_id,
                request_count=0,
                mode="ai",
                status="active",
                last_request_id=None,
            )
            await self._store.save_topic(topic)

            return topic.message_thread_id

    async def register_request(
        self,
        session_id: str | None,
        mode: AIMode | str | None = None,
        status: str = "active",
        request_id: str | None = None,
    ) -> int | None:
        if session_id is None:
            return None

        if not self._config.forum_topics_enabled:
            return None

        async with self._lock:
            topic = await self._store.get_topic(session_id)
            mode_text = self._normalize_mode(mode)
            status_text = self._normalize_status(status)
            short_session_id = self._build_short_session_id(session_id)

            if topic is None:
                topic = await self._create_topic(
                    session_id=session_id,
                    request_count=1,
                    mode=mode_text,
                    status=status_text,
                    last_request_id=request_id,
                )
                await self._store.save_topic(topic)
                return topic.message_thread_id

            topic.request_count += 1
            topic.mode = mode_text
            topic.status = status_text
            topic.short_session_id = short_session_id
            topic.last_request_id = request_id
            topic.name = self._build_topic_name(
                request_count=topic.request_count,
                mode=topic.mode,
                status=topic.status,
                short_session_id=topic.short_session_id,
            )

            await self._store.save_topic(topic)
            await self._try_update_topic_name(topic)

            return topic.message_thread_id

    async def update_request_status(
        self,
        session_id: str | None,
        status: str,
        mode: AIMode | str | None = None,
        request_id: str | None = None,
    ) -> int | None:
        if session_id is None:
            return None

        if not self._config.forum_topics_enabled:
            return None

        async with self._lock:
            topic = await self._store.get_topic(session_id)

            if topic is None:
                return None

            topic.status = self._normalize_status(status)

            if mode is not None:
                topic.mode = self._normalize_mode(mode)

            if request_id is not None:
                topic.last_request_id = request_id

            topic.name = self._build_topic_name(
                request_count=topic.request_count,
                mode=topic.mode,
                status=topic.status,
                short_session_id=topic.short_session_id,
            )

            await self._store.save_topic(topic)
            await self._try_update_topic_name(topic)

            return topic.message_thread_id


    async def _create_topic(
        self,
        session_id: str,
        request_count: int = 0,
        mode: AIMode | str | None = None,
        status: str = "active",
        last_request_id: str | None = None,
    ) -> MiraTelegramTopic:
        bot_api_client = self._get_bot_api_client()
        chat_id = self._get_chat_id()
        mode_text = self._normalize_mode(mode)
        status_text = self._normalize_status(status)
        short_session_id = self._build_short_session_id(session_id)

        topic_name = self._build_topic_name(
            request_count=request_count,
            mode=mode_text,
            status=status_text,
            short_session_id=short_session_id,
        )
        icon_custom_emoji_id = await self._pick_topic_icon_custom_emoji_id(
            session_id=session_id,
        )
        icon_color = self._pick_topic_icon_color(session_id)

        message_thread_id = await bot_api_client.create_forum_topic(
            chat_id=chat_id,
            name=topic_name,
            icon_custom_emoji_id=icon_custom_emoji_id,
            icon_color=icon_color,
        )

        await self._try_delete_system_message(
            chat_id=chat_id,
            message_id=message_thread_id,
        )

        return MiraTelegramTopic(
            session_id=session_id,
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            name=topic_name,
            icon_custom_emoji_id=icon_custom_emoji_id,
            request_count=request_count,
            mode=mode_text,
            status=status_text,
            short_session_id=short_session_id,
            pinned_message_id=None,
            last_request_id=last_request_id,
        )

    def _get_bot_api_client(self) -> MiraTelegramBotApiClient:
        if self._bot_api_client is not None:
            return self._bot_api_client

        if not self._config.bot_token:
            raise RuntimeError(
                "AI_PROVIDER_MIRA_TELEGRAM_BOT_TOKEN is required to create forum topics"
            )

        self._bot_api_client = MiraTelegramBotApiClient(
            bot_token=self._config.bot_token,
        )

        return self._bot_api_client

    def _get_chat_id(self) -> str | int:
        if self._config.chat_id is None:
            raise RuntimeError(
                "AI_PROVIDER_MIRA_TELEGRAM_CHAT_ID is required to create forum topics"
            )

        return self._config.chat_id

    def _build_topic_name(
        self,
        request_count: int,
        mode: str,
        status: str,
        short_session_id: str,
    ) -> str:
        safe_count = max(0, request_count)
        safe_mode = self._safe_compact_text(mode) or "ai"
        safe_status = self._safe_compact_text(status) or "active"
        safe_short_id = self._safe_compact_text(short_session_id) or "unknown"

        name = f"#{safe_count} · {safe_mode} · {safe_status} · {safe_short_id}"

        return name[:128]

    async def _try_update_topic_name(
        self,
        topic: MiraTelegramTopic,
    ) -> None:
        try:
            await self._get_bot_api_client().edit_forum_topic(
                chat_id=topic.chat_id,
                message_thread_id=topic.message_thread_id,
                name=topic.name,
            )
        except Exception:
            return

    async def _try_delete_system_message(
        self,
        chat_id: str | int,
        message_id: int | None,
    ) -> None:
        if message_id is None:
            return

        try:
            await self._get_bot_api_client().delete_message(
                chat_id=chat_id,
                message_id=message_id,
            )
        except Exception:
            return

    async def _pick_topic_icon_custom_emoji_id(
        self,
        session_id: str,
    ) -> str | None:
        icons = await self._get_available_topic_icons()

        if not icons:
            return None

        index = self._stable_index(
            value=session_id,
            modulo=len(icons),
        )

        return icons[index].custom_emoji_id

    def _pick_topic_icon_color(
        self,
        session_id: str,
    ) -> int:
        index = self._stable_index(
            value=session_id,
            modulo=len(DEFAULT_TOPIC_ICON_COLORS),
        )

        return DEFAULT_TOPIC_ICON_COLORS[index]

    async def _get_available_topic_icons(self) -> list[MiraTelegramTopicIcon]:
        if self._available_icons is not None:
            return self._available_icons

        bot_api_client = self._get_bot_api_client()

        try:
            self._available_icons = await bot_api_client.get_forum_topic_icon_stickers()
        except Exception:
            self._available_icons = []

        return self._available_icons

    def _build_short_session_id(
        self,
        session_id: str,
    ) -> str:
        safe_session_id = self._safe_session_id(session_id)

        if safe_session_id.startswith("session_"):
            safe_session_id = safe_session_id.removeprefix("session_")

        if len(safe_session_id) > 8:
            safe_session_id = safe_session_id[:8]

        if not safe_session_id:
            safe_session_id = "unknown"

        return f"s:{safe_session_id}"

    def _normalize_mode(
        self,
        mode: AIMode | str | None,
    ) -> str:
        if mode is None:
            return "ai"

        value = getattr(mode, "value", mode)

        if not isinstance(value, str):
            return "ai"

        value = value.strip().lower()

        if not value:
            return "ai"

        return value

    def _normalize_status(
        self,
        status: str,
    ) -> str:
        value = status.strip().lower()

        aliases = {
            "done": "finished",
            "success": "finished",
            "ok": "finished",
            "failed": "error",
            "failure": "error",
        }

        value = aliases.get(value, value)

        if value in {"active", "waiting", "finished", "error", "closed"}:
            return value

        return "active"

    def _safe_compact_text(
        self,
        value: str,
    ) -> str:
        compact = value.strip().lower()
        compact = re.sub(r"[^a-zA-Z0-9:_-]+", "_", compact)
        compact = compact.strip("_")

        return compact[:24]

    def _stable_index(
        self,
        value: str,
        modulo: int,
    ) -> int:
        if modulo <= 0:
            return 0

        digest = hashlib.sha256(value.encode("utf-8")).digest()

        return int.from_bytes(digest[:2], byteorder="big") % modulo

    def _safe_session_id(
        self,
        session_id: str,
    ) -> str:
        value = session_id.strip()

        if not value:
            return "empty"

        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)
    

