import asyncio
import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.infrastructure.telegram_debug.config import TelegramVisualDebugConfig
from app.infrastructure.telegram_debug.models import TelegramDebugTopic


DEFAULT_TOPIC_ICON_COLORS = [
    0x6FB9F0,
    0xFFD67E,
    0xCB86DB,
    0x8EEE98,
    0xFF93B2,
    0xFB6F5F,
]


@dataclass(slots=True)
class TelegramDebugTopicIcon:
    emoji: str | None
    custom_emoji_id: str


class TelegramDebugTopicStore:
    def get(
        self,
        session_id: str,
        chat_id: int | str,
    ) -> TelegramDebugTopic | None:
        raise NotImplementedError

    def save(
        self,
        topic: TelegramDebugTopic,
    ) -> None:
        raise NotImplementedError


class FileTelegramDebugTopicStore(TelegramDebugTopicStore):
    def __init__(
        self,
        path: str,
    ) -> None:
        self._path = Path(path)

    def get(
        self,
        session_id: str,
        chat_id: int | str,
    ) -> TelegramDebugTopic | None:
        data = self._read_data()
        item = data.get(session_id)

        if not isinstance(item, dict):
            return None

        if str(item.get("chat_id")) != str(chat_id):
            return None

        try:
            return TelegramDebugTopic(
                session_id=str(item["session_id"]),
                chat_id=item["chat_id"],
                message_thread_id=int(item["message_thread_id"]),
                title=str(item["title"]),
                icon_custom_emoji_id=_read_optional_string(
                    item.get("icon_custom_emoji_id")
                ),
                emoji_key=str(item.get("emoji_key") or ""),
                created_at=str(item["created_at"]),
                updated_at=str(item["updated_at"]),
                metadata=dict(item.get("metadata") or {}),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def save(
        self,
        topic: TelegramDebugTopic,
    ) -> None:
        data = self._read_data()
        data[topic.session_id] = asdict(topic)
        self._write_data(data)

    def _read_data(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
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


class TelegramDebugBotApiClient:
    def __init__(
        self,
        bot_token: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._bot_token = bot_token
        self._timeout_seconds = timeout_seconds

    async def create_forum_topic(
        self,
        chat_id: int | str,
        name: str,
        icon_custom_emoji_id: str | None = None,
        icon_color: int | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "name": name,
        }

        if icon_custom_emoji_id:
            payload["icon_custom_emoji_id"] = icon_custom_emoji_id
        elif icon_color is not None:
            payload["icon_color"] = icon_color

        data = await self._post("createForumTopic", payload)
        result = data.get("result")

        if not isinstance(result, dict):
            raise RuntimeError("Telegram createForumTopic returned invalid result")

        thread_id = result.get("message_thread_id")

        if not isinstance(thread_id, int):
            raise RuntimeError("Telegram createForumTopic did not return thread id")

        return thread_id

    async def edit_forum_topic(
        self,
        chat_id: int | str,
        message_thread_id: int,
        name: str | None = None,
        icon_custom_emoji_id: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }

        if name is not None:
            payload["name"] = name

        if icon_custom_emoji_id is not None:
            payload["icon_custom_emoji_id"] = icon_custom_emoji_id

        await self._post("editForumTopic", payload)

    async def get_forum_topic_icon_stickers(self) -> list[TelegramDebugTopicIcon]:
        data = await self._post("getForumTopicIconStickers", {})
        result = data.get("result")

        if not isinstance(result, list):
            return []

        icons: list[TelegramDebugTopicIcon] = []

        for item in result:
            if not isinstance(item, dict):
                continue

            custom_emoji_id = item.get("custom_emoji_id")
            emoji = item.get("emoji")

            if not isinstance(custom_emoji_id, str) or not custom_emoji_id:
                continue

            icons.append(
                TelegramDebugTopicIcon(
                    emoji=emoji if isinstance(emoji, str) else None,
                    custom_emoji_id=custom_emoji_id,
                )
            )

        return icons

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        message_thread_id: int | None = None,
        disable_web_page_preview: bool = True,
        parse_mode: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }

        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id

        if parse_mode:
            payload["parse_mode"] = parse_mode

        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
            payload["allow_sending_without_reply"] = True

        data = await self._post("sendMessage", payload)
        result = data.get("result")

        if not isinstance(result, dict):
            raise RuntimeError("Telegram sendMessage returned invalid result")

        message_id = result.get("message_id")

        if not isinstance(message_id, int):
            raise RuntimeError("Telegram sendMessage did not return message id")

        return message_id

    async def send_photo(
        self,
        chat_id: int | str,
        photo: str,
        caption: str | None = None,
        message_thread_id: int | None = None,
        parse_mode: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
        }

        if caption:
            payload["caption"] = caption

        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id

        if parse_mode:
            payload["parse_mode"] = parse_mode

        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
            payload["allow_sending_without_reply"] = True

        photo_path = Path(photo)

        if photo_path.exists() and photo_path.is_file():
            data = await self._post_multipart(
                method="sendPhoto",
                payload=payload,
                file_field="photo",
                file_path=photo_path,
            )
        else:
            payload["photo"] = photo
            data = await self._post("sendPhoto", payload)

        result = data.get("result")

        if not isinstance(result, dict):
            raise RuntimeError("Telegram sendPhoto returned invalid result")

        message_id = result.get("message_id")

        if not isinstance(message_id, int):
            raise RuntimeError("Telegram sendPhoto did not return message id")

        return message_id

    async def send_document(
        self,
        chat_id: int | str,
        document: str,
        caption: str | None = None,
        message_thread_id: int | None = None,
        parse_mode: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
        }

        if caption:
            payload["caption"] = caption

        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id

        if parse_mode:
            payload["parse_mode"] = parse_mode

        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
            payload["allow_sending_without_reply"] = True

        document_path = Path(document)

        if document_path.exists() and document_path.is_file():
            data = await self._post_multipart(
                method="sendDocument",
                payload=payload,
                file_field="document",
                file_path=document_path,
            )
        else:
            payload["document"] = document
            data = await self._post("sendDocument", payload)

        result = data.get("result")

        if not isinstance(result, dict):
            raise RuntimeError("Telegram sendDocument returned invalid result")

        message_id = result.get("message_id")

        if not isinstance(message_id, int):
            raise RuntimeError("Telegram sendDocument did not return message id")

        return message_id

    async def pin_chat_message(
        self,
        chat_id: int | str,
        message_id: int,
        disable_notification: bool = True,
    ) -> None:
        await self._post(
            "pinChatMessage",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "disable_notification": disable_notification,
            },
        )

    async def _post(
        self,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._post_sync,
            method,
            payload,
        )

    async def _post_multipart(
        self,
        method: str,
        payload: dict[str, Any],
        file_field: str,
        file_path: Path,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._post_multipart_sync,
            method,
            payload,
            file_field,
            file_path,
        )

    def _post_multipart_sync(
        self,
        method: str,
        payload: dict[str, Any],
        file_field: str,
        file_path: Path,
    ) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self._bot_token}/{method}"
        boundary = self._build_multipart_boundary(method, file_path)

        body = self._build_multipart_body(
            payload=payload,
            file_field=file_field,
            file_path=file_path,
            boundary=boundary,
        )

        request = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raw_error = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Telegram {method} failed: {error.code} {raw_error}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Telegram {method} failed: {error}") from error

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"Telegram {method} returned invalid JSON"
            ) from error

        if not isinstance(data, dict):
            raise RuntimeError(f"Telegram {method} returned invalid response")

        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} returned error: {data}")

        return data

    def _build_multipart_boundary(
        self,
        method: str,
        file_path: Path,
    ) -> str:
        source = f"{method}:{file_path}:{datetime.now(timezone.utc).isoformat()}"
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()

        return f"td-{digest[:32]}"

    def _build_multipart_body(
        self,
        payload: dict[str, Any],
        file_field: str,
        file_path: Path,
        boundary: str,
    ) -> bytes:
        chunks: list[bytes] = []

        for key, value in payload.items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode("utf-8"),
                    (
                        f'Content-Disposition: form-data; name="{key}"'
                        "\r\n\r\n"
                    ).encode("utf-8"),
                    str(value).encode("utf-8"),
                    b"\r\n",
                ]
            )

        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{file_field}"; '
                    f'filename="{file_path.name}"\r\n'
                ).encode("utf-8"),
                b"Content-Type: image/jpeg\r\n\r\n",
                file_path.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
        )

        return b"".join(chunks)

    def _post_sync(
        self,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self._bot_token}/{method}"
        body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Telegram Bot API HTTP {exc.code}: {error_body}"
            ) from exc

        data = json.loads(response_body)

        if not data.get("ok"):
            raise RuntimeError(f"Telegram Bot API error: {data}")

        return data


class TelegramDebugTopicManager:
    def __init__(
        self,
        config: TelegramVisualDebugConfig,
        store: TelegramDebugTopicStore | None = None,
        bot_api_client: TelegramDebugBotApiClient | None = None,
    ) -> None:
        self._config = config
        self._store = store or FileTelegramDebugTopicStore(
            config.topic_store_path,
        )
        self._bot_api_client = bot_api_client
        self._lock = asyncio.Lock()
        self._available_icons: list[TelegramDebugTopicIcon] | None = None

    async def get_or_create_topic(
        self,
        session_id: str | None,
        request_id: str | None = None,
        event_title: str | None = None,
        event_date: str | None = None,
    ) -> TelegramDebugTopic | None:
        return await self.prepare_topic_for_message(
            session_id=session_id,
            request_id=request_id,
            provider_name=None,
            status="active",
            event_title=event_title,
            event_date=event_date,
            increment_message_count=False,
        )

    async def prepare_topic_for_message(
        self,
        session_id: str | None,
        request_id: str | None = None,
        provider_name: str | None = None,
        status: str | None = None,
        event_title: str | None = None,
        event_date: str | None = None,
        increment_message_count: bool = True,
    ) -> TelegramDebugTopic | None:
        if not self._config.enabled:
            return None

        if self._config.chat_id is None:
            return None

        async with self._lock:
            return await self._prepare_topic_for_message_locked(
                session_id=session_id,
                request_id=request_id,
                provider_name=provider_name,
                status=status,
                event_title=event_title,
                event_date=event_date,
                increment_message_count=increment_message_count,
            )

    async def _prepare_topic_for_message_locked(
        self,
        session_id: str | None,
        request_id: str | None,
        provider_name: str | None,
        status: str | None,
        event_title: str | None,
        event_date: str | None,
        increment_message_count: bool,
    ) -> TelegramDebugTopic | None:
        normalized_session_id = self._normalize_session_id(
            session_id=session_id,
            request_id=request_id,
        )

        topic = self._store.get(
            session_id=normalized_session_id,
            chat_id=self._config.chat_id,
        )

        message_count = self._read_message_count(topic)

        if increment_message_count or topic is None:
            message_count += 1

        provider = self._clean_title_part(
            provider_name or self._read_topic_metadata(topic, "provider_name")
        ) or "unknown"
        current_status = self._clean_title_part(
            status or self._read_topic_metadata(topic, "status")
        ) or "active"
        current_event_title = self._clean_title_part(
            event_title or self._read_topic_metadata(topic, "event_title")
        ) or "AI session"
        current_event_date = self._clean_title_part(
            event_date or self._read_topic_metadata(topic, "event_date")
        ) or _today_short()

        title = self._build_topic_title(
            message_count=message_count,
            provider_name=provider,
            status=current_status,
            event_date=current_event_date,
            event_title=current_event_title,
        )

        now = _utc_now()

        if topic is None:
            if not self._config.create_topics_enabled:
                return None

            client = self._get_bot_api_client()

            if client is None:
                return None

            icon = await self._pick_topic_icon(normalized_session_id)
            icon_custom_emoji_id = icon.custom_emoji_id if icon is not None else None
            icon_color = self._pick_topic_icon_color(normalized_session_id)

            message_thread_id = await client.create_forum_topic(
                chat_id=self._config.chat_id,
                name=title,
                icon_custom_emoji_id=icon_custom_emoji_id,
                icon_color=icon_color,
            )

            topic = TelegramDebugTopic(
                session_id=normalized_session_id,
                chat_id=self._config.chat_id,
                message_thread_id=message_thread_id,
                title=title,
                icon_custom_emoji_id=icon_custom_emoji_id,
                emoji_key=(
                    icon.emoji
                    if icon is not None and icon.emoji
                    else (icon.custom_emoji_id if icon is not None else "")
                ),
                created_at=now,
                updated_at=now,
                metadata={
                    "request_id": request_id,
                    "provider_name": provider,
                    "status": current_status,
                    "event_title": current_event_title,
                    "event_date": current_event_date,
                    "message_count": message_count,
                    "icon_custom_emoji_id": icon_custom_emoji_id,
                    "icon_emoji": icon.emoji if icon is not None else None,
                    "icon_color": icon_color,
                },
            )
            self._store.save(topic)

            return topic

        previous_title = topic.title
        topic.title = title
        topic.updated_at = now
        topic.metadata = {
            **topic.metadata,
            "request_id": request_id,
            "provider_name": provider,
            "status": current_status,
            "event_title": current_event_title,
            "event_date": current_event_date,
            "message_count": message_count,
        }

        self._store.save(topic)

        if previous_title != title:
            await self._edit_topic_title_safely(topic)

        return topic

    def save_topic(
        self,
        topic: TelegramDebugTopic,
    ) -> None:
        self._store.save(topic)

    async def _edit_topic_title_safely(
        self,
        topic: TelegramDebugTopic,
    ) -> None:
        topic.metadata = {
            **topic.metadata,
            "telegram_topic_rename_skipped": True,
            "telegram_topic_rename_skip_reason": (
                "editForumTopic is disabled because Telegram creates visible service "
                "messages when a forum topic is renamed."
            ),
        }
        self._store.save(topic)

    def _get_bot_api_client(self) -> TelegramDebugBotApiClient | None:
        if self._bot_api_client is not None:
            return self._bot_api_client

        if not self._config.bot_token:
            return None

        self._bot_api_client = TelegramDebugBotApiClient(
            bot_token=self._config.bot_token,
            timeout_seconds=self._config.send_timeout_seconds,
        )

        return self._bot_api_client

    def _normalize_session_id(
        self,
        session_id: str | None,
        request_id: str | None,
    ) -> str:
        if session_id and session_id.strip():
            return session_id.strip()

        if request_id and request_id.strip():
            return f"request:{request_id.strip()}"

        return "session:unknown"

    def _build_topic_title(
        self,
        message_count: int,
        provider_name: str,
        status: str,
        event_date: str,
        event_title: str,
    ) -> str:
        raw_title = (
            f"#{message_count}  {provider_name}  {status}  "
            f"{event_date} {event_title}"
        )

        return self._limit_title(raw_title)

    def _clean_title_part(
        self,
        value: str | None,
    ) -> str:
        if not value:
            return ""

        cleaned = " ".join(value.strip().split())
        cleaned = cleaned.replace("\n", " ").replace("\r", " ")

        return cleaned

    def _limit_title(
        self,
        title: str,
    ) -> str:
        limit = max(16, self._config.max_topic_name_length)

        if len(title) <= limit:
            return title

        return title[: limit - 1].rstrip() + ""

    def _read_message_count(
        self,
        topic: TelegramDebugTopic | None,
    ) -> int:
        if topic is None:
            return 0

        value = topic.metadata.get("message_count")

        if isinstance(value, int):
            return max(0, value)

        if isinstance(value, str):
            try:
                return max(0, int(value))
            except ValueError:
                return 0

        return 0

    def _read_topic_metadata(
        self,
        topic: TelegramDebugTopic | None,
        key: str,
    ) -> str | None:
        if topic is None:
            return None

        value = topic.metadata.get(key)

        if isinstance(value, str):
            return value

        return None

    async def _pick_topic_icon(
        self,
        session_id: str,
    ) -> TelegramDebugTopicIcon | None:
        icons = await self._get_available_topic_icons()

        if not icons:
            return None

        index = self._stable_index(
            value=session_id,
            modulo=len(icons),
        )

        return icons[index]

    def _pick_topic_icon_color(
        self,
        session_id: str,
    ) -> int:
        index = self._stable_index(
            value=session_id,
            modulo=len(DEFAULT_TOPIC_ICON_COLORS),
        )

        return DEFAULT_TOPIC_ICON_COLORS[index]

    async def _get_available_topic_icons(self) -> list[TelegramDebugTopicIcon]:
        if self._available_icons is not None:
            return self._available_icons

        client = self._get_bot_api_client()

        if client is None:
            self._available_icons = []
            return self._available_icons

        try:
            raw_icons = await client.get_forum_topic_icon_stickers()
            self._available_icons = self._normalize_topic_icons(raw_icons)
        except Exception:
            self._available_icons = []

        return self._available_icons

    def _normalize_topic_icons(
        self,
        raw_icons: Any,
    ) -> list[TelegramDebugTopicIcon]:
        if not isinstance(raw_icons, list):
            return []

        icons: list[TelegramDebugTopicIcon] = []

        for item in raw_icons:
            if isinstance(item, TelegramDebugTopicIcon):
                icons.append(item)
                continue

            if not isinstance(item, dict):
                continue

            custom_emoji_id = item.get("custom_emoji_id")
            emoji = item.get("emoji")

            if not isinstance(custom_emoji_id, str) or not custom_emoji_id:
                continue

            icons.append(
                TelegramDebugTopicIcon(
                    emoji=emoji if isinstance(emoji, str) else None,
                    custom_emoji_id=custom_emoji_id,
                )
            )

        return icons

    def _stable_index(
        self,
        value: str,
        modulo: int,
    ) -> int:
        if modulo <= 0:
            return 0

        digest = hashlib.sha256(value.encode("utf-8")).digest()

        return int.from_bytes(digest[:2], byteorder="big") % modulo


def _read_optional_string(
    value: Any,
) -> str | None:
    if isinstance(value, str) and value:
        return value

    return None


def _today_short() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
