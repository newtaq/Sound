import asyncio
import html
import json
import re
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.infrastructure.telegram_debug.config import TelegramVisualDebugConfig
from app.infrastructure.telegram_debug.models import (
    TelegramDebugMessage,
    TelegramDebugMessageKind,
    TelegramDebugTopic,
)
from app.infrastructure.telegram_debug.topics import (
    TelegramDebugBotApiClient,
    TelegramDebugTopicManager,
)


TELEGRAM_TEXT_MESSAGE_LIMIT = 4096
TELEGRAM_MEDIA_CAPTION_LIMIT = 950
DEFAULT_SAFE_MESSAGE_LIMIT = 3900
DETAILS_TITLE = "Полная информация:"
MAX_DETAIL_STRING_LENGTH = 1200
MAX_TEXT_PREVIEW_LENGTH = 1800


@dataclass(slots=True)
class TelegramDebugOutgoingChunk:
    text: str
    parse_mode: str | None
    photo: str | None = None
    send_as_document: bool = False


class TelegramVisualDebugSink:
    def __init__(
        self,
        config: TelegramVisualDebugConfig,
        topic_manager: TelegramDebugTopicManager | None = None,
        bot_api_client: TelegramDebugBotApiClient | None = None,
    ) -> None:
        self._config = config
        self._bot_api_client = bot_api_client
        self._topic_manager = topic_manager or TelegramDebugTopicManager(
            config=config,
            bot_api_client=bot_api_client,
        )
        self._queue: deque[TelegramDebugMessage] = deque()
        self._worker_task: asyncio.Task[None] | None = None
        self._worker_lock = asyncio.Lock()
        self._emit_order_lock = asyncio.Lock()

    async def emit(
        self,
        message: TelegramDebugMessage,
    ) -> None:
        async with self._emit_order_lock:
            await self._emit_now(message)

    async def _emit_now(
        self,
        message: TelegramDebugMessage,
    ) -> None:
        if not self._can_emit():
            return

        if self._should_skip_message(message):
            return

        client = self._get_bot_api_client()

        if client is None:
            return

        self._last_refreshed_thread_id = None

        topic = await self._topic_manager.prepare_topic_for_message(
            session_id=self._read_topic_session_id(message),
            request_id=message.request_id,
            provider_name=message.provider_name,
            status=self._read_topic_status(message),
            event_title=self._read_event_title(message),
            event_date=self._read_event_date(message),
        )

        thread_id = topic.message_thread_id if topic is not None else None
        reply_to_message_id = self._read_reply_to_message_id(
            message=message,
            topic=topic,
        )

        chunks = self._build_outgoing_chunks(message)
        message = self._enable_tool_step_media(message)
        chunks = self._attach_media_to_first_chunk(message, chunks)

        self._write_photo_debug_event(
            action="build_photo_chunk",
            message=message,
            data={
                "has_photo_chunk": any(chunk.photo for chunk in chunks),
                "photo": next((chunk.photo for chunk in chunks if chunk.photo), None),
            },
        )

        for index, chunk in enumerate(chunks):
            chunk_reply_to_message_id = (
                reply_to_message_id if index == 0 else None
            )

            sent_message_id: int | None = None

            if chunk.photo:
                self._write_photo_debug_event(
                    action="before_send_photo",
                    message=message,
                    data={
                        "photo": chunk.photo,
                        "path_exists": Path(chunk.photo).exists(),
                        "path_is_file": Path(chunk.photo).is_file(),
                    },
                )

                try:
                    if chunk.send_as_document:
                        sent_message_id = await self._send_document_with_thread_fallback(
                            message=message,
                            client=client,
                            document=chunk.photo,
                            caption=chunk.text or None,
                            thread_id=thread_id,
                            parse_mode=chunk.parse_mode,
                            reply_to_message_id=chunk_reply_to_message_id,
                        )
                    else:
                        sent_message_id = await self._send_photo_with_thread_fallback(
                            message=message,
                            client=client,
                            photo=chunk.photo,
                            caption=chunk.text or None,
                            thread_id=thread_id,
                            parse_mode=chunk.parse_mode,
                            reply_to_message_id=chunk_reply_to_message_id,
                        )

                    self._write_photo_debug_event(
                        action="after_send_photo_success",
                        message=message,
                        data={
                            "photo": chunk.photo,
                            "sent_message_id": sent_message_id,
                        },
                    )
                except Exception as error:
                    self._write_photo_debug_event(
                        action="send_photo_error",
                        message=message,
                        data={
                            "photo": chunk.photo,
                            "error": str(error),
                        },
                    )

                    error_text = self._escape(
                        self._short_text(str(error), limit=700)
                    )
                    photo_text = self._escape(chunk.photo)

                    fallback_text = self._join_html_parts(
                        chunk.text,
                        (
                            " <b>Медиа афиши не отправилось</b>\n"
                            f"Путь: <code>{photo_text}</code>\n"
                            f"Ошибка: <code>{error_text}</code>"
                        ),
                    )

                    sent_message_id = await self._send_message_with_thread_refresh(
                        message=message,
                        client=client,
                        text=fallback_text,
                        thread_id=thread_id,
                        parse_mode="HTML",
                        reply_to_message_id=chunk_reply_to_message_id,
                    )
            else:
                sent_message_id = await self._send_message_with_thread_refresh(
                    message=message,
                    client=client,
                    text=chunk.text,
                    thread_id=thread_id,
                    parse_mode=chunk.parse_mode,
                    reply_to_message_id=chunk_reply_to_message_id,
                )

            fresh_thread_id = getattr(self, "_last_refreshed_thread_id", None)

            if isinstance(fresh_thread_id, int):
                thread_id = fresh_thread_id

            if index == 0 and topic is not None and sent_message_id is not None:
                await self._remember_and_pin_message(
                    topic=topic,
                    message=message,
                    sent_message_id=sent_message_id,
                )

    async def _send_message_with_thread_refresh(
        self,
        message: TelegramDebugMessage,
        client: TelegramDebugBotApiClient,
        text: str,
        thread_id: int | None,
        parse_mode: str | None,
        reply_to_message_id: int | None,
    ) -> int:
        try:
            return await client.send_message(
                chat_id=self._config.chat_id,
                text=text,
                message_thread_id=thread_id,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception as error:
            if not self._is_thread_not_found_error(error):
                raise

            fresh_thread_id = await self._refresh_topic_after_thread_error(
                message=message,
                client=client,
            )

            return await client.send_message(
                chat_id=self._config.chat_id,
                text=text,
                message_thread_id=fresh_thread_id,
                parse_mode=parse_mode,
                reply_to_message_id=None,
            )

    async def _send_photo_with_thread_fallback(
        self,
        message: TelegramDebugMessage,
        client: TelegramDebugBotApiClient,
        photo: str,
        caption: str | None,
        thread_id: int | None,
        parse_mode: str | None,
        reply_to_message_id: int | None,
    ) -> int:
        try:
            return await client.send_photo(
                chat_id=self._config.chat_id,
                photo=photo,
                caption=caption,
                message_thread_id=thread_id,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception as error:
            if not self._is_thread_not_found_error(error):
                raise

            fresh_thread_id = await self._refresh_topic_after_thread_error(
                message=message,
                client=client,
            )

            return await client.send_photo(
                chat_id=self._config.chat_id,
                photo=photo,
                caption=caption,
                message_thread_id=fresh_thread_id,
                parse_mode=parse_mode,
                reply_to_message_id=None,
            )

    async def _send_document_with_thread_fallback(
        self,
        message: TelegramDebugMessage,
        client: TelegramDebugBotApiClient,
        document: str,
        caption: str | None,
        thread_id: int | None,
        parse_mode: str | None,
        reply_to_message_id: int | None,
    ) -> int:
        try:
            return await client.send_document(
                chat_id=self._config.chat_id,
                document=document,
                caption=caption,
                message_thread_id=thread_id,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception as error:
            if not self._is_thread_not_found_error(error):
                raise

            fresh_thread_id = await self._refresh_topic_after_thread_error(
                message=message,
                client=client,
            )

            return await client.send_document(
                chat_id=self._config.chat_id,
                document=document,
                caption=caption,
                message_thread_id=fresh_thread_id,
                parse_mode=parse_mode,
                reply_to_message_id=None,
            )

    async def _refresh_topic_after_thread_error(
        self,
        message: TelegramDebugMessage,
        client: TelegramDebugBotApiClient,
    ) -> int:
        self._drop_cached_debug_topics()

        self._topic_manager = TelegramDebugTopicManager(
            config=self._config,
            bot_api_client=client,
        )

        topic = await self._topic_manager.prepare_topic_for_message(
            session_id=self._read_topic_session_id(message),
            request_id=message.request_id,
            provider_name=message.provider_name,
            status=self._read_topic_status(message),
            event_title=self._read_event_title(message),
            event_date=self._read_event_date(message),
        )

        if topic is None or topic.message_thread_id is None:
            raise RuntimeError("Could not recreate Telegram debug topic")

        self._last_refreshed_thread_id = topic.message_thread_id

        return topic.message_thread_id

    def _is_thread_not_found_error(
        self,
        error: Exception,
    ) -> bool:
        return "message thread not found" in str(error).lower()

    def _drop_cached_debug_topics(self) -> None:
        cache_path = Path(".runtime") / "telegram_debug_topics.json"

        try:
            cache_path.unlink(missing_ok=True)
        except Exception:
            pass

    async def flush(self) -> None:
        task = self._worker_task

        if task is not None and not task.done():
            await task

        if self._queue:
            await self._drain_queue()

        self._worker_task = None

    async def _drain_queue(self) -> None:
        async with self._worker_lock:
            while self._queue:
                message = self._queue.popleft()

                try:
                    await self.emit(message)
                except Exception as error:
                    self._write_queue_error_event(
                        message=message,
                        error=error,
                    )

    def _write_queue_error_event(
        self,
        message: TelegramDebugMessage,
        error: Exception,
    ) -> None:
        log_path = Path(".runtime") / "telegram_debug_errors.log"

        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)

            payload = {
                "action": "emit_background_error",
                "kind": str(message.kind.value if hasattr(message.kind, "value") else message.kind),
                "session_id": message.session_id,
                "request_id": message.request_id,
                "provider_name": message.provider_name,
                "event_title": message.event_title,
                "step_type": message.metadata.get("step_type"),
                "summary_ready": message.metadata.get("summary_ready"),
                "poster_event_summary": message.metadata.get("poster_event_summary"),
                "telegram_debug_send_photo": message.metadata.get("telegram_debug_send_photo"),
                "telegram_debug_photo_path": message.metadata.get("telegram_debug_photo_path"),
                "error_type": type(error).__name__,
                "error": str(error),
            }

            with log_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            return

    def emit_background(
        self,
        message: TelegramDebugMessage,
    ) -> None:
        if not self._can_emit():
            return

        if self._should_skip_message(message):
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        self._queue.append(message)

        if self._worker_task is None or self._worker_task.done():
            self._worker_task = loop.create_task(self._drain_queue())
    async def _remember_and_pin_message(
        self,
        topic: TelegramDebugTopic,
        message: TelegramDebugMessage,
        sent_message_id: int,
    ) -> None:
        should_save = False

        if not topic.metadata.get("first_message_id"):
            topic.metadata = {
                **topic.metadata,
                "first_message_id": sent_message_id,
            }
            should_save = True

            if not self._read_metadata_bool(message.metadata, "skip_pin"):
                await self._pin_message_safely(
                    chat_id=topic.chat_id,
                    message_id=sent_message_id,
                )

        if message.kind == TelegramDebugMessageKind.REQUEST:
            topic.metadata = {
                **topic.metadata,
                "request_message_id": sent_message_id,
            }
            should_save = True

        if should_save:
            self._topic_manager.save_topic(topic)
    async def _pin_message_safely(
        self,
        chat_id: int | str,
        message_id: int,
    ) -> None:
        client = self._get_bot_api_client()

        if client is None:
            return

        if not hasattr(client, "pin_chat_message"):
            return

        try:
            await client.pin_chat_message(
                chat_id=chat_id,
                message_id=message_id,
                disable_notification=True,
            )
        except Exception:
            return
    def _build_outgoing_chunks(
        self,
        message: TelegramDebugMessage,
    ) -> list[TelegramDebugOutgoingChunk]:
        parse_mode = self._read_parse_mode(message)

        if parse_mode != "HTML":
            text = self._format_plain_message(message)
            return [
                TelegramDebugOutgoingChunk(
                    text=chunk,
                    parse_mode=parse_mode,
                )
                for chunk in self._split_plain_text(text, self._message_limit())
            ]

        if self._read_metadata_bool(message.metadata, "raw_text"):
            text = (message.text or message.kind.value or "").strip()

            if self._looks_like_ready_html_message(text):
                return self._split_ready_html_message(text)

            return [
                TelegramDebugOutgoingChunk(
                    text=chunk,
                    parse_mode=None,
                )
                for chunk in self._split_plain_text(text, self._message_limit())
            ]

        if self._is_agent_step_message(message):
            return self._build_agent_step_html_chunks(message)

        return self._build_default_html_chunks(message)
    def _build_agent_step_html_chunks(
        self,
        message: TelegramDebugMessage,
    ) -> list[TelegramDebugOutgoingChunk]:
        text = (message.text or message.kind.value or "").strip()

        if self._looks_like_ready_html_message(text):
            return self._split_ready_html_message(text)

        title, body = self._split_first_line(text)
        summary, details = self._split_details_block(body)

        title_html = self._bold(title or message.kind.value)
        summary_html = self._format_visible_html(summary)

        prepared_details = self._prepare_details_text(details)

        if not prepared_details:
            return self._split_ready_html_message(
                self._join_html_parts(title_html, summary_html)
            )

        return self._build_html_message_with_details_chunks(
            title_html=title_html,
            body_html=summary_html,
            details_text=prepared_details,
            continuation_title=title or message.kind.value,
        )
    def _build_default_html_chunks(
        self,
        message: TelegramDebugMessage,
    ) -> list[TelegramDebugOutgoingChunk]:
        main_text = (message.text or message.kind.value or "").strip()
        title, body = self._split_first_line(main_text)

        title_html = self._bold(title or message.kind.value)
        body_html = self._format_visible_html(body)
        details_text = self._build_details_text(message)

        if not details_text:
            return self._split_ready_html_message(
                self._join_html_parts(title_html, body_html)
            )

        return self._build_html_message_with_details_chunks(
            title_html=title_html,
            body_html=body_html,
            details_text=details_text,
            continuation_title=title or message.kind.value,
        )
    def _build_html_message_with_details_chunks(
        self,
        title_html: str,
        body_html: str,
        details_text: str,
        continuation_title: str,
    ) -> list[TelegramDebugOutgoingChunk]:
        details_text = self._prepare_details_text(details_text)
        limit = self._message_limit()

        if not details_text:
            return [
                TelegramDebugOutgoingChunk(
                    text=self._join_html_parts(title_html, body_html),
                    parse_mode="HTML",
                )
            ]

        first_prefix = self._join_html_parts(
            title_html,
            body_html,
            DETAILS_TITLE,
        )
        first_wrapper_size = self._details_wrapper_size(first_prefix)
        first_available = max(200, limit - first_wrapper_size)

        detail_chunks = self._split_text_for_html_block(
            text=details_text,
            limit=first_available,
        )

        if not detail_chunks:
            return [
                TelegramDebugOutgoingChunk(
                    text=self._join_html_parts(title_html, body_html),
                    parse_mode="HTML",
                )
            ]

        result: list[TelegramDebugOutgoingChunk] = []

        result.append(
            TelegramDebugOutgoingChunk(
                text=self._join_html_parts(
                    first_prefix,
                    self._blockquote(detail_chunks[0]),
                ),
                parse_mode="HTML",
            )
        )

        for index, detail_chunk in enumerate(detail_chunks[1:], start=2):
            prefix = self._join_html_parts(
                self._bold(f"{continuation_title} — продолжение {index}"),
                DETAILS_TITLE,
            )

            result.append(
                TelegramDebugOutgoingChunk(
                    text=self._join_html_parts(
                        prefix,
                        self._blockquote(detail_chunk),
                    ),
                    parse_mode="HTML",
                )
            )

        return result

    def _can_emit(self) -> bool:
        enabled = getattr(self._config, "enabled", True)

        if not enabled:
            return False

        chat_id = getattr(self._config, "chat_id", None)

        return chat_id is not None

    def _should_skip_message(
        self,
        message: TelegramDebugMessage,
    ) -> bool:
        metadata = message.metadata

        if metadata.get("telegram_debug_skip"):
            return True

        if metadata.get("skip_telegram_debug"):
            return True

        if metadata.get("agent_run") or metadata.get("agent_step"):
            return False

        provider_values = {
            str(getattr(message, "provider_name", "") or "").lower(),
            str(metadata.get("provider_name") or "").lower(),
            str(metadata.get("provider") or "").lower(),
            str(metadata.get("requested_provider") or "").lower(),
        }

        if "groq_search" in provider_values:
            return True

        if metadata.get("agent_tool") == "groq_search":
            return True

        if metadata.get("purpose") == "find_candidate_sources":
            return True

        return False

    def _build_photo_chunk(
        self,
        message: TelegramDebugMessage,
    ) -> str | None:
        paths = self._read_attachment_paths(message)
        return paths[0] if paths else None

    async def _send_attached_files(
        self,
        message: TelegramDebugMessage,
        thread_id: int | None,
        reply_to_message_id: int | None,
    ) -> None:
        if not self._should_attach_files(message):
            return

        paths = self._read_attachment_paths(message)

        if not paths:
            self._write_photo_debug_log(
                action="no_attachment_paths",
                message=message,
                data={},
            )
            return

        for index, file_path in enumerate(paths, start=1):
            await self._send_one_attachment(
                message=message,
                file_path=file_path,
                thread_id=thread_id,
                reply_to_message_id=reply_to_message_id,
                index=index,
                total=len(paths),
            )

    async def _send_one_attachment(
        self,
        message: TelegramDebugMessage,
        file_path: str,
        thread_id: int | None,
        reply_to_message_id: int | None,
        index: int,
        total: int,
    ) -> None:
        client = self._get_bot_api_client()

        if client is None:
            return

        real_path = Path(file_path)

        self._write_photo_debug_log(
            action="before_send_attachment",
            message=message,
            data={
                "file_path": str(real_path),
                "path_exists": real_path.exists(),
                "path_is_file": real_path.is_file(),
                "index": index,
                "total": total,
            },
        )

        if not real_path.is_file():
            return

        caption = self._escape(
            self._build_attachment_caption(
                message=message,
                file_path=str(real_path),
                index=index,
                total=total,
            )
        )

        suffix = real_path.suffix.lower()
        is_photo = suffix in {".jpg", ".jpeg", ".png", ".webp"}

        if is_photo and hasattr(client, "send_photo"):
            try:
                sent_message_id = await self._call_send_photo(
                    client=client,
                    path=str(real_path),
                    caption=caption,
                    thread_id=thread_id,
                    reply_to_message_id=reply_to_message_id,
                )
                self._write_photo_debug_log(
                    action="after_send_photo_success",
                    message=message,
                    data={
                        "file_path": str(real_path),
                        "sent_message_id": sent_message_id,
                        "index": index,
                        "total": total,
                    },
                )
                return
            except Exception as exc:
                self._write_photo_debug_log(
                    action="send_photo_error",
                    message=message,
                    data={
                        "file_path": str(real_path),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "index": index,
                        "total": total,
                    },
                )

        if hasattr(client, "send_document"):
            try:
                sent_message_id = await self._call_send_document(
                    client=client,
                    path=str(real_path),
                    caption=caption,
                    thread_id=thread_id,
                    reply_to_message_id=reply_to_message_id,
                )
                self._write_photo_debug_log(
                    action="after_send_document_success",
                    message=message,
                    data={
                        "file_path": str(real_path),
                        "sent_message_id": sent_message_id,
                        "index": index,
                        "total": total,
                    },
                )
            except Exception as exc:
                self._write_photo_debug_log(
                    action="send_document_error",
                    message=message,
                    data={
                        "file_path": str(real_path),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "index": index,
                        "total": total,
                    },
                )

    def _read_attachment_paths(
        self,
        message: TelegramDebugMessage,
    ) -> list[str]:
        metadata = message.metadata or {}
        result: list[str] = []

        list_keys = [
            "telegram_debug_file_paths",
            "tool_file_paths",
            "used_file_paths",
            "attachment_paths",
            "media_paths",
            "file_paths",
        ]

        for key in list_keys:
            value = metadata.get(key)

            if isinstance(value, str):
                result.append(value)

            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        result.append(item)
                    elif isinstance(item, dict):
                        nested_path = item.get("path") or item.get("file_path")
                        if isinstance(nested_path, str):
                            result.append(nested_path)

        single_keys = [
            "telegram_debug_photo_path",
            "poster_path",
            "photo_path",
            "file_path",
        ]

        for key in single_keys:
            value = metadata.get(key)

            if isinstance(value, str):
                result.append(value)

        cleaned: list[str] = []
        seen: set[str] = set()

        for item in result:
            stripped = item.strip()

            if not stripped:
                continue

            key = stripped.lower()

            if key in seen:
                continue

            seen.add(key)
            cleaned.append(stripped)

        return cleaned

    def _should_attach_files(
        self,
        message: TelegramDebugMessage,
    ) -> bool:
        metadata = message.metadata or {}
        step_type = str(metadata.get("step_type") or "")

        if metadata.get("telegram_debug_send_photo") is True:
            return True

        if step_type in {"tool_call", "tool_result", "event_summary"}:
            return True

        return False

    def _build_attachment_caption(
        self,
        message: TelegramDebugMessage,
        file_path: str,
        index: int,
        total: int,
    ) -> str:
        metadata = message.metadata or {}
        step_type = str(metadata.get("step_type") or "")
        tool_name = str(metadata.get("tool_name") or "").strip()

        if step_type == "tool_call":
            title = "Файл, переданный в инструмент"
        elif step_type == "tool_result":
            title = "Файл, использованный инструментом"
        elif step_type == "event_summary":
            title = "Медиа финальной афиши"
        else:
            title = "Прикреплённый файл"

        if tool_name:
            title = f"{title}: {tool_name}"

        if total > 1:
            title = f"{title} ({index}/{total})"

        return self._short_text(f"{title}\n{file_path}", 900)

    async def _call_send_photo(
        self,
        client,
        path: str,
        caption: str,
        thread_id: int | None,
        reply_to_message_id: int | None,
    ) -> int:
        variants = [
            {
                "chat_id": self._config.chat_id,
                "photo": path,
                "caption": caption,
                "message_thread_id": thread_id,
                "parse_mode": "HTML",
                "reply_to_message_id": reply_to_message_id,
            },
            {
                "chat_id": self._config.chat_id,
                "photo": path,
                "caption": caption,
                "message_thread_id": thread_id,
                "parse_mode": "HTML",
            },
            {
                "chat_id": self._config.chat_id,
                "photo": path,
                "caption": caption,
                "message_thread_id": thread_id,
            },
            {
                "chat_id": self._config.chat_id,
                "photo": path,
                "caption": caption,
            },
            {
                "chat_id": self._config.chat_id,
                "photo": path,
            },
        ]

        last_error: TypeError | None = None

        for kwargs in variants:
            try:
                return await client.send_photo(**kwargs)
            except TypeError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error

        raise RuntimeError("send_photo failed")

    async def _call_send_document(
        self,
        client,
        path: str,
        caption: str,
        thread_id: int | None,
        reply_to_message_id: int | None,
    ) -> int:
        variants = [
            {
                "chat_id": self._config.chat_id,
                "document": path,
                "caption": caption,
                "message_thread_id": thread_id,
                "parse_mode": "HTML",
                "reply_to_message_id": reply_to_message_id,
            },
            {
                "chat_id": self._config.chat_id,
                "document": path,
                "caption": caption,
                "message_thread_id": thread_id,
                "parse_mode": "HTML",
            },
            {
                "chat_id": self._config.chat_id,
                "document": path,
                "caption": caption,
                "message_thread_id": thread_id,
            },
            {
                "chat_id": self._config.chat_id,
                "document": path,
                "caption": caption,
            },
            {
                "chat_id": self._config.chat_id,
                "document": path,
            },
        ]

        last_error: TypeError | None = None

        for kwargs in variants:
            try:
                return await client.send_document(**kwargs)
            except TypeError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error

        raise RuntimeError("send_document failed")

    def _write_photo_debug_log(
        self,
        action: str,
        message: TelegramDebugMessage,
        data: dict[str, Any],
    ) -> None:
        try:
            log_path = Path(".runtime") / "telegram_debug_photo.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            payload = {
                "action": action,
                "kind": getattr(message.kind, "value", str(message.kind)),
                "session_id": message.session_id,
                "request_id": message.request_id,
                "provider_name": message.provider_name,
                "event_title": self._read_event_title(message),
                "step_type": (message.metadata or {}).get("step_type"),
                "telegram_debug_send_photo": (message.metadata or {}).get("telegram_debug_send_photo"),
                "telegram_debug_photo_path": (message.metadata or {}).get("telegram_debug_photo_path"),
                "poster_path": (message.metadata or {}).get("poster_path"),
                "data": data,
            }

            with log_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        except Exception:
            return

    def _short_text(
        self,
        value: str,
        limit: int,
    ) -> str:
        if len(value) <= limit:
            return value

        return value[: max(0, limit - 3)] + "..."

    def _split_message(
        self,
        text: str,
        limit: int = 3500,
    ) -> list[str]:
        if not text:
            return [""]

        chunks: list[str] = []
        current = ""

        for line in text.splitlines(keepends=True):
            if len(line) > limit:
                if current:
                    chunks.append(current.rstrip())
                    current = ""

                for index in range(0, len(line), limit):
                    chunks.append(line[index:index + limit].rstrip())

                continue

            if len(current) + len(line) > limit:
                if current:
                    chunks.append(current.rstrip())

                current = line
            else:
                current += line

        if current:
            chunks.append(current.rstrip())

        return chunks or [""]

    def _get_bot_api_client(self) -> TelegramDebugBotApiClient | None:
        if self._bot_api_client is not None:
            return self._bot_api_client

        bot_token = getattr(self._config, "bot_token", None)

        if not bot_token:
            return None

        self._bot_api_client = TelegramDebugBotApiClient(
            bot_token=bot_token,
        )

        return self._bot_api_client

    def _write_photo_debug_event(
        self,
        action: str,
        message: TelegramDebugMessage,
        data: dict[str, Any],
    ) -> None:
        log_path = Path(".runtime") / "telegram_debug_photo.log"

        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)

            payload = {
                "action": action,
                "kind": str(message.kind.value if hasattr(message.kind, "value") else message.kind),
                "session_id": message.session_id,
                "request_id": message.request_id,
                "step_type": message.metadata.get("step_type"),
                "telegram_debug_send_photo": message.metadata.get(
                    "telegram_debug_send_photo"
                ),
                "telegram_debug_photo_path": message.metadata.get(
                    "telegram_debug_photo_path"
                ),
                "poster_path": message.metadata.get("poster_path"),
                "data": data,
            }

            with log_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            return

    def _enable_tool_step_media(
        self,
        message: TelegramDebugMessage,
    ) -> TelegramDebugMessage:
        step_type = self._read_metadata_string(message.metadata, "step_type")

        if step_type not in {"tool_call", "tool_result"}:
            return message

        if self._read_metadata_bool(message.metadata, "telegram_debug_send_photo"):
            return message

        media_path = (
            self._read_metadata_string(message.metadata, "telegram_debug_photo_path")
            or self._read_metadata_string(message.metadata, "poster_path")
        )

        if not media_path:
            return message

        try:
            path = Path(media_path)
        except Exception:
            return message

        try:
            if not path.is_file():
                return message
        except OSError:
            return message

        suffix = path.suffix.lower()

        metadata = {
            **message.metadata,
            "telegram_debug_send_photo": True,
            "telegram_debug_photo_path": media_path,
            "telegram_debug_media_source": "tool_step_existing_media_path",
            "telegram_debug_send_media_as_document": suffix not in {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
            },
        }

        if not metadata.get("telegram_debug_media_caption"):
            metadata["telegram_debug_media_caption"] = (
                "Файл, который использовался на этом шаге инструмента"
            )

        return replace(message, metadata=metadata)

    def _attach_media_to_first_chunk(
        self,
        message: TelegramDebugMessage,
        chunks: list[TelegramDebugOutgoingChunk],
    ) -> list[TelegramDebugOutgoingChunk]:
        photo = self._build_photo_chunk(message)

        if photo is None:
            return chunks

        if not chunks:
            return chunks

        send_as_document = self._read_metadata_bool(
            message.metadata,
            "telegram_debug_send_media_as_document",
        )

        first_chunk = chunks[0]
        first_text = first_chunk.text or ""

        if len(first_text) <= TELEGRAM_MEDIA_CAPTION_LIMIT:
            return [
                replace(
                    first_chunk,
                    photo=photo,
                    send_as_document=send_as_document,
                ),
                *chunks[1:],
            ]

        return self._build_media_with_text_continuation_chunks(
            message=message,
            chunks=chunks,
            photo=photo,
            send_as_document=send_as_document,
        )

    def _build_media_with_text_continuation_chunks(
        self,
        message: TelegramDebugMessage,
        chunks: list[TelegramDebugOutgoingChunk],
        photo: str,
        send_as_document: bool,
    ) -> list[TelegramDebugOutgoingChunk]:
        plain_text = self._plain_text_from_chunks(chunks)

        if not plain_text:
            plain_text = self._default_media_caption(message, photo)

        caption_limit = TELEGRAM_MEDIA_CAPTION_LIMIT
        split_index = self._find_split_index(plain_text, caption_limit)

        caption = plain_text[:split_index].rstrip()
        rest = plain_text[split_index:].lstrip()

        if not caption:
            caption = self._default_media_caption(message, photo)
            rest = plain_text

        result = [
            TelegramDebugOutgoingChunk(
                text=caption,
                parse_mode=None,
                photo=photo,
                send_as_document=send_as_document,
            )
        ]

        if not rest:
            return result

        title, _ = self._split_first_line(plain_text)
        continuation_title = title or self._read_media_continuation_title(message)
        continuation_limit = self._message_limit()

        for index, chunk in enumerate(
            self._split_plain_text_with_prefix(
                text=rest,
                prefix=f"{continuation_title} — продолжение",
                limit=continuation_limit,
            ),
            start=2,
        ):
            result.append(
                TelegramDebugOutgoingChunk(
                    text=f"{continuation_title} — продолжение {index}\n\n{chunk}",
                    parse_mode=None,
                )
            )

        return result

    def _split_plain_text_with_prefix(
        self,
        text: str,
        prefix: str,
        limit: int,
    ) -> list[str]:
        available = max(200, limit - len(prefix) - 16)

        return self._split_plain_text(text, available)

    def _plain_text_from_chunks(
        self,
        chunks: list[TelegramDebugOutgoingChunk],
    ) -> str:
        text = "\n\n".join(
            chunk.text.strip()
            for chunk in chunks
            if chunk.text and chunk.text.strip()
        )

        if not text:
            return ""

        text = re.sub(
            r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            lambda match: html.unescape(match.group(2) or match.group(1)),
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = self._strip_known_html(text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        text = self._strip_repeated_empty_lines(text)

        return text.strip()

    def _default_media_caption(
        self,
        message: TelegramDebugMessage,
        photo: str,
    ) -> str:
        step_type = self._read_metadata_string(message.metadata, "step_type") or ""
        tool_name = self._read_metadata_string(message.metadata, "tool_name")

        if step_type in {"tool_call", "tool_result"} and tool_name:
            return f"{tool_name}: файл шага\n{photo}"

        if step_type == "event_summary":
            return f"Медиа финальной афиши\n{photo}"

        return f"Прикреплённый файл\n{photo}"

    def _read_media_continuation_title(
        self,
        message: TelegramDebugMessage,
    ) -> str:
        step_type = self._read_metadata_string(message.metadata, "step_type") or ""
        step_index = message.metadata.get("step_index")
        step_total = message.metadata.get("step_total")
        tool_name = self._read_metadata_string(message.metadata, "tool_name")

        if step_type in {"tool_call", "tool_result"}:
            if isinstance(step_index, int) and isinstance(step_total, int):
                if tool_name:
                    return f"TOOL #{step_index}/{step_total}: {tool_name}"

                return f"TOOL #{step_index}/{step_total}"

            if tool_name:
                return f"TOOL: {tool_name}"

        if step_type:
            return step_type.upper()

        return str(message.kind.value if hasattr(message.kind, "value") else message.kind)

    def _split_ready_html_message(
        self,
        text: str,
    ) -> list[TelegramDebugOutgoingChunk]:
        limit = self._message_limit()

        if len(text) <= limit:
            return [
                TelegramDebugOutgoingChunk(
                    text=text,
                    parse_mode="HTML",
                )
            ]

        plain = self._strip_known_html(text)

        return [
            TelegramDebugOutgoingChunk(
                text=chunk,
                parse_mode="HTML",
            )
            for chunk in self._build_plain_as_html_continuation_chunks(plain)
        ]

    def _build_plain_as_html_continuation_chunks(
        self,
        text: str,
    ) -> list[str]:
        title, body = self._split_first_line(text)
        summary, details = self._split_details_block(body)

        if details:
            chunks = self._build_html_message_with_details_chunks(
                title_html=self._bold(title),
                body_html=self._format_visible_html(summary),
                details_text=details,
                continuation_title=title,
            )
            return [chunk.text for chunk in chunks]

        escaped_chunks = self._split_text_for_html_block(
            text=body,
            limit=max(200, self._message_limit() - len(title) - 32),
        )

        result: list[str] = []

        for index, chunk in enumerate(escaped_chunks, start=1):
            chunk_title = title if index == 1 else f"{title} — продолжение {index}"
            result.append(
                self._join_html_parts(
                    self._bold(chunk_title),
                    self._format_visible_html(chunk),
                )
            )

        return result

    def _format_message(
        self,
        message: TelegramDebugMessage,
    ) -> str:
        chunks = self._build_outgoing_chunks(message)

        return "\n\n".join(chunk.text for chunk in chunks)

    def _format_plain_message(
        self,
        message: TelegramDebugMessage,
    ) -> str:
        main_text = (message.text or message.kind.value or "").strip()

        if self._is_agent_step_message(message):
            return main_text

        details = self._build_details_text(message)

        if details:
            return f"{main_text}\n\n{DETAILS_TITLE}\n{details}".strip()

        return main_text

    def _build_details_text(
        self,
        message: TelegramDebugMessage,
    ) -> str:
        lines: list[str] = []

        self._append_plain_detail_if_present(lines, 0, "provider", message.provider_name)
        self._append_plain_detail_if_present(lines, 0, "session", message.session_id)
        self._append_plain_detail_if_present(lines, 0, "request", message.request_id)

        event_title = self._read_event_title(message)
        event_date = self._read_event_date(message)

        self._append_plain_detail_if_present(lines, 0, "event", event_title)
        self._append_plain_detail_if_present(lines, 0, "date", event_date)

        metadata = self._compact_detail_value(message.metadata)

        if isinstance(metadata, dict) and metadata:
            lines.append("• metadata:")
            self._append_plain_metadata(lines, 1, metadata)

        return self._prepare_details_text("\n".join(lines))

    def _append_plain_detail_if_present(
        self,
        lines: list[str],
        level: int,
        key: str,
        value: object,
    ) -> None:
        if self._is_empty_detail_value(value):
            return

        self._append_plain_detail(lines, level, key, value)

    def _append_plain_detail(
        self,
        lines: list[str],
        level: int,
        key: str,
        value: object,
    ) -> None:
        indent = "  " * level
        lines.append(f"{indent}• {key}: {self._stringify_plain_value(value)}")

    def _append_plain_metadata(
        self,
        lines: list[str],
        level: int,
        value: object,
    ) -> None:
        if self._is_empty_detail_value(value):
            return

        indent = "  " * level

        if isinstance(value, dict):
            for key, nested_value in value.items():
                if self._is_empty_detail_value(nested_value):
                    continue

                if isinstance(nested_value, dict | list):
                    lines.append(f"{indent}• {key}:")
                    self._append_plain_metadata(lines, level + 1, nested_value)
                else:
                    lines.append(
                        f"{indent}• {key}: "
                        f"{self._stringify_plain_value(nested_value)}"
                    )
            return

        if isinstance(value, list):
            for index, item in enumerate(value, start=1):
                if self._is_empty_detail_value(item):
                    continue

                if isinstance(item, dict | list):
                    lines.append(f"{indent}• item {index}:")
                    self._append_plain_metadata(lines, level + 1, item)
                else:
                    lines.append(f"{indent}• {self._stringify_plain_value(item)}")
            return

        lines.append(f"{indent}• {self._stringify_plain_value(value)}")

    def _compact_detail_value(
        self,
        value: Any,
    ) -> Any:
        value = self._to_jsonable(value)

        if isinstance(value, dict):
            if "pages" in value and isinstance(value["pages"], list):
                return {
                    **{
                        key: self._compact_detail_value(nested_value)
                        for key, nested_value in value.items()
                        if key != "pages"
                        and not self._is_empty_detail_value(nested_value)
                    },
                    "pages": [
                        self._compact_page(item)
                        for item in value["pages"]
                        if isinstance(item, dict)
                    ],
                }

            if "text" in value and isinstance(value["text"], str):
                result = {
                    key: self._compact_detail_value(nested_value)
                    for key, nested_value in value.items()
                    if key != "text"
                    and not self._is_empty_detail_value(nested_value)
                }
                preview = self._compact_text_preview(value["text"])

                if preview:
                    result["text_preview"] = preview

                return result

            result: dict[str, Any] = {}

            for key, nested_value in value.items():
                compact_value = self._compact_detail_value(nested_value)

                if self._is_empty_detail_value(compact_value):
                    continue

                result[str(key)] = compact_value

            return result

        if isinstance(value, list):
            result = []

            for item in value:
                compact_item = self._compact_detail_value(item)

                if not self._is_empty_detail_value(compact_item):
                    result.append(compact_item)

            return result

        if isinstance(value, str):
            return self._compact_text_preview(value)

        return value

    def _compact_page(
        self,
        page: dict[str, Any],
    ) -> dict[str, Any]:
        keys = [
            "url",
            "ok",
            "status_code",
            "blocked_by_antibot",
            "final_url",
            "content_type",
            "title",
            "description",
            "text_preview",
            "error",
        ]

        result: dict[str, Any] = {}

        for key in keys:
            value = page.get(key)

            if self._is_empty_detail_value(value):
                continue

            if key in {"text_preview", "description"} and isinstance(value, str):
                result[key] = self._compact_text_preview(value)
            elif key == "final_url" and isinstance(value, str):
                result[key] = self._truncate(value, 900)
            else:
                result[key] = self._compact_detail_value(value)

        return result

    def _compact_text_preview(
        self,
        value: str,
    ) -> str:
        text = value.strip()

        if not text:
            return ""

        text = self._drop_markdown_tables(text)
        text = self._strip_repeated_empty_lines(text)
        text = self._normalize_inline_whitespace(text)

        return self._truncate(text, MAX_TEXT_PREVIEW_LENGTH)

    def _stringify_plain_value(
        self,
        value: object,
    ) -> str:
        if value is None:
            return "null"

        if isinstance(value, bool):
            return "true" if value else "false"

        text = str(value)
        text = self._drop_markdown_tables(text)
        text = self._strip_repeated_empty_lines(text)

        return self._truncate(text, MAX_DETAIL_STRING_LENGTH)

    def _prepare_details_text(
        self,
        details: str,
    ) -> str:
        text = details.strip()

        if not text:
            return ""

        parsed = self._try_parse_json(text)

        if parsed is not None:
            text = self._format_details_value(self._compact_detail_value(parsed))

        text = self._drop_markdown_tables(text)
        text = self._strip_repeated_empty_lines(text)

        return text.strip()

    def _format_details_value(
        self,
        value: Any,
        level: int = 0,
    ) -> str:
        lines: list[str] = []
        self._append_plain_metadata(lines, level, value)

        return "\n".join(lines)

    def _try_parse_json(
        self,
        text: str,
    ) -> Any | None:
        stripped = text.strip()

        if not stripped.startswith(("{", "[")):
            return None

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None

    def _format_visible_html(
        self,
        text: str,
    ) -> str:
        if not text or not text.strip():
            return ""

        segments = self._split_markdown_table_segments(text)
        parts: list[str] = []

        for segment_type, segment_text in segments:
            if not segment_text.strip():
                continue

            if segment_type == "table":
                parts.append(self._pre(segment_text.strip()))
            else:
                parts.append(self._escape_with_basic_markdown(segment_text.strip()))

        return "\n\n".join(parts)

    def _escape_with_basic_markdown(
        self,
        text: str,
    ) -> str:
        prepared = text
        prepared = re.sub(r"<(https?://[^>\s]+)>", r"\1", prepared)
        prepared = prepared.replace("```", "")

        escaped = self._escape(prepared)

        escaped = re.sub(
            r"\*\*([^*\n][^*]*?)\*\*",
            r"<b>\1</b>",
            escaped,
        )
        escaped = re.sub(
            r"`([^`\n]+?)`",
            r"<code>\1</code>",
            escaped,
        )

        return self._linkify_escaped_urls(escaped)

    def _drop_markdown_tables(
        self,
        text: str,
    ) -> str:
        segments = self._split_markdown_table_segments(text)
        parts: list[str] = []

        for segment_type, segment_text in segments:
            if segment_type == "table":
                continue

            if segment_text.strip():
                parts.append(segment_text)

        return "\n".join(parts).strip()

    def _split_markdown_table_segments(
        self,
        text: str,
    ) -> list[tuple[str, str]]:
        lines = text.splitlines()
        result: list[tuple[str, str]] = []
        buffer: list[str] = []
        index = 0

        while index < len(lines):
            if self._is_markdown_table_start(lines, index):
                if buffer:
                    result.append(("text", "\n".join(buffer).strip()))
                    buffer = []

                table_lines = [lines[index], lines[index + 1]]
                index += 2

                while index < len(lines) and self._is_markdown_table_row(lines[index]):
                    table_lines.append(lines[index])
                    index += 1

                result.append(("table", "\n".join(table_lines).strip()))
                continue

            buffer.append(lines[index])
            index += 1

        if buffer:
            result.append(("text", "\n".join(buffer).strip()))

        return result

    def _is_markdown_table_start(
        self,
        lines: list[str],
        index: int,
    ) -> bool:
        if index + 1 >= len(lines):
            return False

        return self._is_markdown_table_row(lines[index]) and self._is_table_separator(
            lines[index + 1]
        )

    def _is_markdown_table_row(
        self,
        line: str,
    ) -> bool:
        stripped = line.strip()

        if not stripped:
            return False

        return stripped.count("|") >= 2

    def _is_table_separator(
        self,
        line: str,
    ) -> bool:
        stripped = line.strip()

        if stripped.count("|") < 2:
            return False

        without_pipes = stripped.replace("|", "").strip()

        if not without_pipes:
            return False

        return all(char in "-: " for char in without_pipes)

    def _split_details_block(
        self,
        text: str,
    ) -> tuple[str, str]:
        if not text:
            return "", ""

        marker_match = re.search(
            rf"(?im)^\s*{re.escape(DETAILS_TITLE)}\s*$",
            text,
        )

        if marker_match is None:
            return text.strip(), ""

        summary = text[: marker_match.start()].strip()
        details = text[marker_match.end() :].strip()

        return summary, details

    def _split_first_line(
        self,
        text: str,
    ) -> tuple[str, str]:
        stripped = text.strip()

        if not stripped:
            return "", ""

        lines = stripped.splitlines()

        if not lines:
            return "", ""

        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        return title, body

    def _read_reply_to_message_id(
        self,
        message: TelegramDebugMessage,
        topic: TelegramDebugTopic | None,
    ) -> int | None:
        if topic is None:
            return None

        if message.kind not in {
            TelegramDebugMessageKind.RESPONSE,
            TelegramDebugMessageKind.STREAM_FINISHED,
            TelegramDebugMessageKind.ERROR,
            TelegramDebugMessageKind.TOOL_RESULT,
        }:
            return None

        return self._read_metadata_int(
            topic.metadata,
            "request_message_id",
        ) or self._read_metadata_int(
            topic.metadata,
            "first_message_id",
        )

    def _read_topic_session_id(
        self,
        message: TelegramDebugMessage,
    ) -> str | None:
        return (
            self._read_metadata_string(message.metadata, "telegram_debug_topic_session_id")
            or self._read_metadata_string(message.metadata, "agent_session_id")
            or self._read_metadata_string(message.metadata, "parent_session_id")
            or self._read_metadata_string(message.metadata, "root_session_id")
            or message.session_id
        )

    def _read_topic_status(
        self,
        message: TelegramDebugMessage,
    ) -> str:
        metadata_status = self._read_metadata_string(
            message.metadata,
            "status",
        )

        if metadata_status:
            return metadata_status

        if message.kind in {
            TelegramDebugMessageKind.REQUEST,
            TelegramDebugMessageKind.STREAM_STARTED,
            TelegramDebugMessageKind.STREAM_DELTA,
            TelegramDebugMessageKind.TOOL_CALL,
        }:
            return "active"

        if message.kind in {
            TelegramDebugMessageKind.RESPONSE,
            TelegramDebugMessageKind.STREAM_FINISHED,
            TelegramDebugMessageKind.TOOL_RESULT,
        }:
            return "finished"

        if message.kind == TelegramDebugMessageKind.ERROR:
            return "error"

        return "active"

    def _read_event_title(
        self,
        message: TelegramDebugMessage,
    ) -> str | None:
        return (
            self._read_metadata_string(message.metadata, "telegram_debug_event_title")
            or self._read_metadata_string(message.metadata, "poster_agent_event_title")
            or self._read_metadata_string(message.metadata, "root_event_title")
            or self._read_metadata_string(message.metadata, "event_title")
            or self._read_metadata_string(message.metadata, "title")
            or message.event_title
        )

    def _read_event_date(
        self,
        message: TelegramDebugMessage,
    ) -> str | None:
        return (
            self._read_metadata_string(message.metadata, "telegram_debug_event_date")
            or self._read_metadata_string(message.metadata, "poster_agent_event_date")
            or self._read_metadata_string(message.metadata, "root_event_date")
            or self._read_metadata_string(message.metadata, "event_date")
            or self._read_metadata_string(message.metadata, "date")
        )

    def _read_parse_mode(
        self,
        message: TelegramDebugMessage,
    ) -> str | None:
        parsed = self._read_metadata_parse_mode(message.metadata)

        if parsed is not _PARSE_MODE_NOT_SET:
            return parsed

        return "HTML"

    def _read_metadata_parse_mode(
        self,
        metadata: dict[str, Any],
    ) -> str | None | object:
        value = self._read_metadata_string(metadata, "parse_mode")

        if value is None:
            return _PARSE_MODE_NOT_SET

        normalized = value.strip().lower()

        if normalized in {"none", "plain", "text", "plain_text"}:
            return None

        if normalized == "html":
            return "HTML"

        if normalized == "markdown":
            return "Markdown"

        if normalized == "markdownv2":
            return "MarkdownV2"

        return "HTML"

    def _read_metadata_string(
        self,
        metadata: dict[str, Any],
        key: str,
    ) -> str | None:
        value = metadata.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

        return None

    def _read_metadata_int(
        self,
        metadata: dict[str, Any],
        key: str,
    ) -> int | None:
        value = metadata.get(key)

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None

        return None

    def _read_metadata_bool(
        self,
        metadata: dict[str, Any],
        key: str,
    ) -> bool:
        value = metadata.get(key)

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {
                "1",
                "true",
                "yes",
                "y",
                "да",
            }

        return False

    def _is_agent_step_message(
        self,
        message: TelegramDebugMessage,
    ) -> bool:
        return self._read_metadata_bool(message.metadata, "agent_step")

    def _looks_like_ready_html_message(
        self,
        text: str,
    ) -> bool:
        if not text:
            return False

        stripped = text.strip().lower()

        if stripped.startswith(("<b>", "<strong>", "<i>", "<u>", "<s>", "<code>", "<pre>")):
            return True

        if "<blockquote" in stripped and "</blockquote>" in stripped:
            return True

        return False

    def _message_limit(self) -> int:
        raw_limit = getattr(
            self._config,
            "max_message_length",
            DEFAULT_SAFE_MESSAGE_LIMIT,
        )

        if not isinstance(raw_limit, int):
            return DEFAULT_SAFE_MESSAGE_LIMIT

        if raw_limit <= 0:
            return DEFAULT_SAFE_MESSAGE_LIMIT

        return min(raw_limit, TELEGRAM_TEXT_MESSAGE_LIMIT)

    def _split_plain_text(
        self,
        text: str,
        limit: int,
    ) -> list[str]:
        if len(text) <= limit:
            return [text]

        result: list[str] = []
        current = text

        while len(current) > limit:
            split_index = self._find_split_index(current, limit)
            result.append(current[:split_index].rstrip())
            current = current[split_index:].lstrip()

        if current:
            result.append(current)

        return result

    def _split_text_for_html_block(
        self,
        text: str,
        limit: int,
    ) -> list[str]:
        if limit <= 0:
            limit = DEFAULT_SAFE_MESSAGE_LIMIT

        result: list[str] = []
        current = text.strip()

        while current:
            split_index = self._find_html_safe_plain_split_index(
                text=current,
                limit=limit,
            )

            result.append(current[:split_index].rstrip())
            current = current[split_index:].lstrip()

        return result

    def _find_html_safe_plain_split_index(
        self,
        text: str,
        limit: int,
    ) -> int:
        if len(self._escape(text)) <= limit:
            return len(text)

        low = 1
        high = min(len(text), limit)
        best = 1

        while low <= high:
            middle = (low + high) // 2

            if len(self._escape(text[:middle])) <= limit:
                best = middle
                low = middle + 1
            else:
                high = middle - 1

        safe = self._find_split_index(text, best)

        if safe <= 0:
            return best

        return safe

    def _find_split_index(
        self,
        text: str,
        limit: int,
    ) -> int:
        if len(text) <= limit:
            return len(text)

        newline_index = text.rfind("\n", 0, limit)

        if newline_index >= max(1, limit // 2):
            return newline_index + 1

        space_index = text.rfind(" ", 0, limit)

        if space_index >= max(1, limit // 2):
            return space_index + 1

        return limit

    def _details_wrapper_size(
        self,
        prefix: str,
    ) -> int:
        return len(
            self._join_html_parts(
                prefix,
                self._blockquote(""),
            )
        )

    def _join_html_parts(
        self,
        *parts: str,
    ) -> str:
        return "\n\n".join(part.strip() for part in parts if part and part.strip())

    def _bold(
        self,
        value: str,
    ) -> str:
        return f"<b>{self._escape(value)}</b>"

    def _pre(
        self,
        value: str,
    ) -> str:
        return f"<pre>{self._escape(value)}</pre>"

    def _blockquote(
        self,
        value: str,
    ) -> str:
        return (
            "<blockquote expandable>"
            f"{self._linkify_escaped_urls(self._escape(value))}"
            "</blockquote>"
        )

    def _linkify_escaped_urls(
        self,
        text: str,
    ) -> str:
        if not text:
            return ""

        return re.sub(
            r"https?://[^\s<]+",
            lambda match: self._build_url_anchor(match.group(0)),
            text,
        )

    def _build_url_anchor(
        self,
        escaped_url: str,
    ) -> str:
        suffix = ""

        while escaped_url and escaped_url[-1] in ".,;:!?)]}":
            suffix = escaped_url[-1] + suffix
            escaped_url = escaped_url[:-1]

        full_url = html.unescape(escaped_url)
        label = self._short_url_label(full_url)
        href = html.escape(full_url, quote=True)
        label_html = self._escape(label)

        return f'<a href="{href}">{label_html}</a>{suffix}'

    def _short_url_label(
        self,
        url: str,
    ) -> str:
        value = url.strip()

        if len(value) <= 72:
            return value

        match = re.match(r"^(https?://[^/?#]+)(/[^?#]*)?", value)

        if match is None:
            return self._truncate(value, 72)

        domain = match.group(1)
        path = (match.group(2) or "").strip("/")
        path_preview = ""

        if path:
            path_preview = "/".join(
                part for part in path.split("/")[:3] if part
            )

        base = domain

        if path_preview:
            base = f"{domain}/{path_preview}"

        query_preview = ""

        if "?" in value:
            first_query_part = value.split("?", 1)[1].split("&", 1)[0].strip()

            if first_query_part:
                query_preview = "?" + self._truncate(first_query_part, 24)

        label = self._truncate(f"{base}{query_preview}", 72)

        if not label.endswith("..."):
            label += "..."

        return label

    def _strip_known_html(
        self,
        text: str,
    ) -> str:
        if not text:
            return ""

        result = text
        result = re.sub(r"<br\s*/?>", "\n", result, flags=re.IGNORECASE)
        result = re.sub(r"</p\s*>", "\n", result, flags=re.IGNORECASE)
        result = re.sub(
            (
                r"</?(?:b|strong|i|em|u|s|strike|del|code|pre|"
                r"blockquote|p)(?:\s+expandable)?\s*>"
            ),
            "",
            result,
            flags=re.IGNORECASE,
        )

        return html.unescape(result).strip()

    def _strip_repeated_empty_lines(
        self,
        text: str,
    ) -> str:
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def _normalize_inline_whitespace(
        self,
        text: str,
    ) -> str:
        lines = []

        for line in text.splitlines():
            lines.append(re.sub(r"[ \t]{2,}", " ", line).strip())

        return "\n".join(line for line in lines if line).strip()

    def _truncate(
        self,
        value: str,
        limit: int,
    ) -> str:
        if len(value) <= limit:
            return value

        return value[: max(0, limit - 3)].rstrip() + "..."

    def _is_empty_detail_value(
        self,
        value: object,
    ) -> bool:
        if value is None:
            return True

        if isinstance(value, str):
            return not value.strip()

        if isinstance(value, dict | list | tuple | set):
            return len(value) == 0

        return False

    def _to_jsonable(
        self,
        value: Any,
    ) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self._to_jsonable(nested_value)
                for key, nested_value in value.items()
            }

        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]

        if isinstance(value, tuple):
            return [self._to_jsonable(item) for item in value]

        if isinstance(value, set):
            return [self._to_jsonable(item) for item in value]

        if isinstance(value, str | int | float | bool) or value is None:
            return value

        return str(value)

    def _escape(
        self,
        value: str | None,
    ) -> str:
        return html.escape(value or "", quote=False)


_PARSE_MODE_NOT_SET = object()

