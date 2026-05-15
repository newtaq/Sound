import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from app.application.contracts import AIResponseAttachment
from app.infrastructure.providers.mira.config import MiraTelegramProviderConfig


@dataclass(slots=True)
class MiraTelegramResponse:
    text: str
    message_ids: list[int] = field(default_factory=list)
    attachments: list[AIResponseAttachment] = field(default_factory=list)
    finish_reason: str = "completed"
    raw_messages: list[Any] = field(default_factory=list, repr=False)


@dataclass(slots=True)
class MiraTelegramStreamUpdate:
    text: str
    full_text: str
    message_ids: list[int] = field(default_factory=list)
    attachments: list[AIResponseAttachment] = field(default_factory=list)
    finish_reason: str | None = None
    is_final: bool = False
    raw_messages: list[Any] = field(default_factory=list, repr=False)


class MiraTelegramResponseWaiter:
    def __init__(
        self,
        tracker: "MiraTelegramResponseTracker",
        client: Any,
        target_chat_id: str | int,
        message_thread_id: int | None,
        timeout_seconds: float,
        collect_timeout_seconds: float = 0.8,
        handler_group: int = 80,
    ) -> None:
        self._tracker = tracker
        self._client = client
        self._target_chat_id = target_chat_id
        self._message_thread_id = message_thread_id
        self._timeout_seconds = timeout_seconds
        self._collect_timeout_seconds = collect_timeout_seconds
        self._handler_group = handler_group

        self._handler: Any | None = None
        self._future: asyncio.Future[MiraTelegramResponse] | None = None
        self._after_message_id: int | None = None
        self._after_message_id_ready = False
        self._pending_messages: list[Any] = []
        self._accepted_messages: list[Any] = []
        self._settle_task: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        if self._handler is not None:
            return

        try:
            from pyrogram.handlers import MessageHandler  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Pyrogram is not installed. Install it with: pip install pyrogram"
            ) from exc

        loop = asyncio.get_running_loop()
        self._future = loop.create_future()

        async def on_message(_: Any, message: Any) -> None:
            self._handle_message(message)

        self._handler = MessageHandler(on_message)
        self._client.add_handler(self._handler, group=self._handler_group)

    async def wait(self, after_message_id: int | None) -> MiraTelegramResponse:
        self._after_message_id = after_message_id
        self._after_message_id_ready = True
        self._try_accept_pending_messages()

        try:
            return await asyncio.wait_for(
                self._require_future(),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            if self._accepted_messages:
                return self._build_response(
                    messages=self._accepted_messages,
                    finish_reason="timeout_with_partial_response",
                )

            return MiraTelegramResponse(
                text="",
                message_ids=[],
                attachments=[],
                finish_reason="timeout",
                raw_messages=[],
            )
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        if self._settle_task is not None:
            self._settle_task.cancel()
            self._settle_task = None

        if self._handler is not None:
            self._client.remove_handler(
                self._handler,
                group=self._handler_group,
            )
            self._handler = None

    def _handle_message(self, message: Any) -> None:
        future = self._require_future()

        if future.done():
            return

        if not self._tracker.is_candidate_response_message(
            message=message,
            target_chat_id=self._target_chat_id,
            message_thread_id=self._message_thread_id,
        ):
            return

        if not self._after_message_id_ready:
            self._pending_messages.append(message)
            return

        if not self._tracker.is_after_message_id(
            message=message,
            after_message_id=self._after_message_id,
        ):
            return

        self._accept_message(message)

    def _try_accept_pending_messages(self) -> None:
        if not self._after_message_id_ready:
            return

        for message in self._pending_messages:
            if not self._tracker.is_after_message_id(
                message=message,
                after_message_id=self._after_message_id,
            ):
                continue

            self._accept_message(message)

        self._pending_messages.clear()

    def _accept_message(self, message: Any) -> None:
        future = self._require_future()

        if future.done():
            return

        text = self._tracker.extract_message_text(message).strip()
        attachments = self._tracker.extract_message_attachments(message)

        if not text and not attachments:
            return

        message_id = getattr(message, "id", None)

        if isinstance(message_id, int):
            for accepted_message in self._accepted_messages:
                if getattr(accepted_message, "id", None) == message_id:
                    return

        self._accepted_messages.append(message)
        self._accepted_messages.sort(key=lambda item: getattr(item, "id", 0))

        self._schedule_settle()

    def _schedule_settle(self) -> None:
        if self._settle_task is not None:
            self._settle_task.cancel()

        self._settle_task = asyncio.create_task(self._settle_and_finish())

    async def _settle_and_finish(self) -> None:
        try:
            await asyncio.sleep(self._collect_timeout_seconds)
        except asyncio.CancelledError:
            return

        future = self._require_future()

        if future.done():
            return

        future.set_result(
            self._build_response(
                messages=self._accepted_messages,
                finish_reason="message_received",
            )
        )

    def _build_response(
        self,
        messages: list[Any],
        finish_reason: str,
    ) -> MiraTelegramResponse:
        return MiraTelegramResponse(
            text=self._tracker.build_response_text(messages),
            message_ids=self._tracker.extract_message_ids(messages),
            attachments=self._tracker.extract_messages_attachments(messages),
            finish_reason=finish_reason,
            raw_messages=list(messages),
        )

    def _require_future(self) -> asyncio.Future[MiraTelegramResponse]:
        if self._future is None:
            raise RuntimeError("MiraTelegramResponseWaiter is not started")

        return self._future


class MiraTelegramResponseTracker:
    def __init__(
        self,
        config: MiraTelegramProviderConfig,
        poll_interval_seconds: float = 0.35,
        history_limit: int = 30,
    ) -> None:
        self._config = config
        self._poll_interval_seconds = poll_interval_seconds
        self._history_limit = history_limit
        self._mira_user_id: int | None = None
        self._mira_username = self._normalize_username(config.bot_username)

    async def prepare_response_waiter(
        self,
        client: Any,
        chat_id: str | int,
        message_thread_id: int | None = None,
    ) -> MiraTelegramResponseWaiter:
        await self._resolve_mira_user(client)

        target_chat_id = await self._resolve_chat_id(
            client=client,
            chat_id=chat_id,
        )

        waiter = MiraTelegramResponseWaiter(
            tracker=self,
            client=client,
            target_chat_id=target_chat_id,
            message_thread_id=message_thread_id,
            timeout_seconds=self._config.request_timeout_seconds,
        )

        await waiter.start()

        return waiter

    async def wait_for_response(
        self,
        client: Any,
        chat_id: str | int,
        after_message_id: int | None,
        message_thread_id: int | None = None,
    ) -> MiraTelegramResponse:
        waiter = await self.prepare_response_waiter(
            client=client,
            chat_id=chat_id,
            message_thread_id=message_thread_id,
        )

        return await waiter.wait(after_message_id=after_message_id)

    async def stream_response(
        self,
        client: Any,
        chat_id: str | int,
        after_message_id: int | None,
        message_thread_id: int | None = None,
    ) -> AsyncIterator[MiraTelegramStreamUpdate]:
        await self._resolve_mira_user(client)

        target_chat_id = await self._resolve_chat_id(
            client=client,
            chat_id=chat_id,
        )

        started_at = time.monotonic()
        last_changed_at = started_at

        last_text = ""
        last_message_ids: list[int] = []
        last_attachments: list[AIResponseAttachment] = []
        last_raw_messages: list[Any] = []

        while True:
            now = time.monotonic()

            if now - started_at >= self._config.request_timeout_seconds:
                finish_reason = (
                    "timeout_with_partial_response"
                    if last_text or last_attachments
                    else "timeout"
                )

                yield MiraTelegramStreamUpdate(
                    text="",
                    full_text=last_text,
                    message_ids=last_message_ids,
                    attachments=last_attachments,
                    finish_reason=finish_reason,
                    is_final=True,
                    raw_messages=last_raw_messages,
                )
                return

            messages = await self._load_response_messages(
                client=client,
                chat_id=chat_id,
                target_chat_id=target_chat_id,
                message_thread_id=message_thread_id,
                after_message_id=after_message_id,
            )

            current_text = self.build_response_text(messages)
            current_message_ids = self.extract_message_ids(messages)
            current_attachments = self.extract_messages_attachments(messages)

            if (
                current_text
                and current_text != last_text
            ) or len(current_attachments) != len(last_attachments):
                delta = self._build_delta(
                    old_text=last_text,
                    new_text=current_text,
                )

                last_text = current_text
                last_message_ids = current_message_ids
                last_attachments = current_attachments
                last_raw_messages = messages
                last_changed_at = now

                yield MiraTelegramStreamUpdate(
                    text=delta,
                    full_text=current_text,
                    message_ids=current_message_ids,
                    attachments=current_attachments,
                    raw_messages=messages,
                )

            if (
                last_text or last_attachments
            ) and now - last_changed_at >= self._config.idle_timeout_seconds:
                yield MiraTelegramStreamUpdate(
                    text="",
                    full_text=last_text,
                    message_ids=last_message_ids,
                    attachments=last_attachments,
                    finish_reason="idle_timeout",
                    is_final=True,
                    raw_messages=last_raw_messages,
                )
                return

            await asyncio.sleep(self._poll_interval_seconds)

    async def _resolve_mira_user(self, client: Any) -> None:
        if self._mira_user_id is not None:
            return

        if not self._mira_username:
            return

        try:
            user = await client.get_users(self._mira_username)
        except Exception:
            return

        user_id = getattr(user, "id", None)
        if isinstance(user_id, int):
            self._mira_user_id = user_id

    async def _resolve_chat_id(
        self,
        client: Any,
        chat_id: str | int,
    ) -> int | str:
        try:
            chat = await client.get_chat(chat_id)
        except Exception:
            return chat_id

        resolved_chat_id = getattr(chat, "id", None)

        if isinstance(resolved_chat_id, int):
            return resolved_chat_id

        return chat_id

    def is_candidate_response_message(
        self,
        message: Any,
        target_chat_id: str | int,
        message_thread_id: int | None,
    ) -> bool:
        message_id = getattr(message, "id", None)

        if not isinstance(message_id, int):
            return False

        if getattr(message, "outgoing", False):
            return False

        if not self._is_target_chat(
            message=message,
            target_chat_id=target_chat_id,
        ):
            return False

        if not self._is_target_thread(
            message=message,
            message_thread_id=message_thread_id,
        ):
            return False

        if not self._is_from_mira(message):
            return False

        if not self._message_has_content(message):
            return False

        return True

    def is_after_message_id(
        self,
        message: Any,
        after_message_id: int | None,
    ) -> bool:
        if after_message_id is None:
            return True

        message_id = getattr(message, "id", None)

        return isinstance(message_id, int) and message_id > after_message_id

    def extract_message_text(self, message: Any) -> str:
        return self._extract_message_text(message)

    def extract_message_attachments(
        self,
        message: Any,
    ) -> list[AIResponseAttachment]:
        attachments: list[AIResponseAttachment] = []

        for kind, media_object in self._iter_message_media(message):
            attachments.append(
                self._build_attachment(
                    message=message,
                    kind=kind,
                    media_object=media_object,
                )
            )

        return attachments

    def extract_message_ids(self, messages: list[Any]) -> list[int]:
        return [
            message_id
            for message_id in (
                getattr(message, "id", None)
                for message in messages
            )
            if isinstance(message_id, int)
        ]

    def extract_messages_attachments(
        self,
        messages: list[Any],
    ) -> list[AIResponseAttachment]:
        attachments: list[AIResponseAttachment] = []

        for message in messages:
            attachments.extend(self.extract_message_attachments(message))

        return attachments

    def build_response_text(self, messages: list[Any]) -> str:
        parts = [
            self._extract_message_text(message).strip()
            for message in messages
        ]

        return "\n\n".join(part for part in parts if part)

    async def _load_response_messages(
        self,
        client: Any,
        chat_id: str | int,
        target_chat_id: str | int,
        message_thread_id: int | None,
        after_message_id: int | None,
    ) -> list[Any]:
        messages: list[Any] = []

        async for message in client.get_chat_history(
            chat_id=chat_id,
            limit=self._history_limit,
        ):
            if not self.is_candidate_response_message(
                message=message,
                target_chat_id=target_chat_id,
                message_thread_id=message_thread_id,
            ):
                continue

            if not self.is_after_message_id(
                message=message,
                after_message_id=after_message_id,
            ):
                continue

            messages.append(message)

        return sorted(messages, key=lambda item: item.id)

    def _is_target_chat(
        self,
        message: Any,
        target_chat_id: str | int,
    ) -> bool:
        chat = getattr(message, "chat", None)
        message_chat_id = getattr(chat, "id", None)

        if message_chat_id == target_chat_id:
            return True

        if isinstance(target_chat_id, str):
            target_username = self._normalize_username(target_chat_id)
            chat_username = self._normalize_username(getattr(chat, "username", None))

            if target_username and chat_username == target_username:
                return True

        return False

    def _is_target_thread(
        self,
        message: Any,
        message_thread_id: int | None,
    ) -> bool:
        current_thread_id = self._extract_message_thread_id(message)

        if message_thread_id is None:
            return current_thread_id is None

        return current_thread_id == message_thread_id

    def _extract_message_thread_id(
        self,
        message: Any,
    ) -> int | None:
        for attr_name in [
            "message_thread_id",
            "top_thread_message_id",
            "reply_to_top_message_id",
        ]:
            value = getattr(message, attr_name, None)
            if isinstance(value, int):
                return value

        reply_to_message = getattr(message, "reply_to_message", None)
        if reply_to_message is not None:
            for attr_name in [
                "message_thread_id",
                "top_thread_message_id",
                "reply_to_top_message_id",
            ]:
                value = getattr(reply_to_message, attr_name, None)
                if isinstance(value, int):
                    return value

        return None

    def _is_from_mira(self, message: Any) -> bool:
        sender = getattr(message, "from_user", None)

        if sender is None:
            return False

        sender_id = getattr(sender, "id", None)
        if self._mira_user_id is not None and sender_id == self._mira_user_id:
            return True

        sender_username = self._normalize_username(getattr(sender, "username", None))
        if self._mira_username and sender_username == self._mira_username:
            return True

        first_name = str(getattr(sender, "first_name", "") or "").strip().lower()
        if (
            not sender_username
            and self._mira_username == "mira"
            and first_name == "mira"
        ):
            return True

        return False

    def _message_has_content(self, message: Any) -> bool:
        if self._extract_message_text(message).strip():
            return True

        return bool(list(self._iter_message_media(message)))

    def _extract_message_text(self, message: Any) -> str:
        text = getattr(message, "text", None)
        caption = getattr(message, "caption", None)

        if text:
            return str(text)

        if caption:
            return str(caption)

        return ""

    def _iter_message_media(
        self,
        message: Any,
    ) -> list[tuple[str, Any]]:
        result: list[tuple[str, Any]] = []

        for kind in [
            "photo",
            "video",
            "animation",
            "document",
            "audio",
            "voice",
            "video_note",
            "sticker",
        ]:
            media_object = getattr(message, kind, None)
            if media_object is not None:
                result.append((kind, media_object))

        return result

    def _build_attachment(
        self,
        message: Any,
        kind: str,
        media_object: Any,
    ) -> AIResponseAttachment:
        chat = getattr(message, "chat", None)

        return AIResponseAttachment(
            kind=kind,
            media_id=self._read_first_string_attr(
                media_object,
                ["file_id", "file_ref", "media_id"],
            ),
            file_unique_id=self._read_first_string_attr(
                media_object,
                ["file_unique_id"],
            ),
            filename=self._read_first_string_attr(
                media_object,
                ["file_name", "filename"],
            ),
            mime_type=self._read_first_string_attr(
                media_object,
                ["mime_type"],
            ),
            file_size=self._read_first_int_attr(
                media_object,
                ["file_size"],
            ),
            caption=self._extract_message_text(message) or None,
            telegram_chat_id=getattr(chat, "id", None),
            telegram_message_id=getattr(message, "id", None),
            metadata={
                "message_thread_id": self._extract_message_thread_id(message),
                "width": self._read_first_int_attr(media_object, ["width"]),
                "height": self._read_first_int_attr(media_object, ["height"]),
                "duration": self._read_first_int_attr(media_object, ["duration"]),
            },
        )

    def _read_first_string_attr(
        self,
        value: Any,
        names: list[str],
    ) -> str | None:
        for name in names:
            attr_value = getattr(value, name, None)
            if isinstance(attr_value, str) and attr_value:
                return attr_value

        return None

    def _read_first_int_attr(
        self,
        value: Any,
        names: list[str],
    ) -> int | None:
        for name in names:
            attr_value = getattr(value, name, None)
            if isinstance(attr_value, int):
                return attr_value

        return None

    def _build_delta(self, old_text: str, new_text: str) -> str:
        if not old_text:
            return new_text

        if new_text.startswith(old_text):
            return new_text[len(old_text):]

        return new_text

    def _normalize_username(self, username: str | None) -> str:
        if not username:
            return ""

        return username.strip().lower().removeprefix("@")
    

