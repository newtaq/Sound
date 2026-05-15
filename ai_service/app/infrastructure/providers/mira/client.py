import asyncio
import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.infrastructure.providers.mira.config import MiraTelegramProviderConfig
from app.infrastructure.providers.mira.request_payload import (
    MiraTelegramAttachment,
    MiraTelegramAttachmentKind,
    MiraTelegramMessageKind,
    MiraTelegramOutgoingMessage,
)


@dataclass(slots=True)
class MiraTelegramSentMessage:
    message_id: int | None
    chat_id: int | str | None
    text: str | None = None
    caption: str | None = None
    message_thread_id: int | None = None
    raw_message: Any = field(default=None, repr=False)


class MiraTelegramClient:
    def __init__(self, config: MiraTelegramProviderConfig) -> None:
        self._config = config
        self._client: Any | None = None
        self._started = False
        self._warmed_chat_ids: set[str | int] = set()
        self._start_lock = asyncio.Lock()

    @property
    def chat_id(self) -> str | int:
        return self._config.chat_id or self._config.bot_username

    @property
    def stream_chat_id(self) -> str | int:
        return self._config.stream_chat_id or self._config.bot_username

    @property
    def raw_client(self) -> Any:
        return self._require_client()

    async def start(self) -> None:
        async with self._start_lock:
            if self._started:
                return

            client = self._client or self._build_client()
            await client.start()

            self._client = client
            self._started = True

            await self._warmup_target_chat(self.chat_id)

    async def stop(self) -> None:
        if not self._client or not self._started:
            return

        await self._client.stop()
        self._started = False
        self._warmed_chat_ids.clear()

    async def send_messages(
        self,
        messages: list[MiraTelegramOutgoingMessage],
        chat_id: str | int | None = None,
        message_thread_id: int | None = None,
    ) -> list[MiraTelegramSentMessage]:
        await self.start()

        target_chat_id = chat_id or self.chat_id
        sent_messages: list[MiraTelegramSentMessage] = []

        for message in messages:
            sent_messages.extend(
                await self.send_message(
                    message=message,
                    chat_id=target_chat_id,
                    message_thread_id=message_thread_id,
                )
            )

        return sent_messages

    async def send_message(
        self,
        message: MiraTelegramOutgoingMessage,
        chat_id: str | int | None = None,
        message_thread_id: int | None = None,
    ) -> list[MiraTelegramSentMessage]:
        await self.start()

        target_chat_id = chat_id or self.chat_id
        await self._warmup_target_chat(target_chat_id)

        if message.kind == MiraTelegramMessageKind.TEXT:
            return [
                await self._send_text(
                    message=message,
                    chat_id=target_chat_id,
                    message_thread_id=message_thread_id,
                )
            ]

        if message.kind == MiraTelegramMessageKind.MEDIA_GROUP:
            return await self._send_media_group(
                message=message,
                chat_id=target_chat_id,
                message_thread_id=message_thread_id,
            )

        return [
            await self._send_single_media(
                message=message,
                chat_id=target_chat_id,
                message_thread_id=message_thread_id,
            )
        ]

    def _build_client(self) -> Any:
        try:
            from pyrogram import Client  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Pyrogram is not installed. Install it with: pip install pyrogram"
            ) from exc

        proxy_config = getattr(self._config, "proxy", None)

        proxy = (
            proxy_config.to_pyrogram_proxy()
            if proxy_config is not None
            else None
        )

        client_kwargs: dict[str, Any] = {
            "name": self._config.session_name,
            "api_id": self._config.api_id,
            "api_hash": self._config.api_hash,
        }

        if proxy is not None:
            client_kwargs["proxy"] = proxy

        if self._config.session_string:
            client_kwargs["session_string"] = self._config.session_string

        return Client(**client_kwargs)

    async def _warmup_target_chat(self, chat_id: str | int | None = None) -> None:
        target_chat_id = chat_id or self.chat_id

        if target_chat_id in self._warmed_chat_ids:
            return

        client = self._require_client()

        try:
            await client.get_chat(target_chat_id)
            self._warmed_chat_ids.add(target_chat_id)
            return
        except Exception:
            pass

        normalized_target_username = self._normalize_username(target_chat_id)

        try:
            async for dialog in client.get_dialogs(limit=200):
                chat = getattr(dialog, "chat", None)

                current_chat_id = getattr(chat, "id", None)
                if current_chat_id == target_chat_id:
                    self._warmed_chat_ids.add(target_chat_id)
                    return

                current_username = self._normalize_username(
                    getattr(chat, "username", None)
                )
                if (
                    normalized_target_username
                    and current_username == normalized_target_username
                ):
                    self._warmed_chat_ids.add(target_chat_id)
                    return
        except Exception:
            pass

    async def _send_text(
        self,
        message: MiraTelegramOutgoingMessage,
        chat_id: str | int,
        message_thread_id: int | None,
    ) -> MiraTelegramSentMessage:
        client = self._require_client()

        send_kwargs: dict[str, Any] = {
            "chat_id": chat_id,
            "text": message.text or "",
            "disable_web_page_preview": True,
        }

        if message_thread_id is not None:
            send_kwargs["message_thread_id"] = message_thread_id

        try:
            raw_message = await client.send_message(**send_kwargs)

            return self._to_sent_message(
                raw_message=raw_message,
                message_thread_id=message_thread_id,
            )
        except TypeError as exc:
            if not self._is_unsupported_message_thread_error(exc):
                raise

            if message_thread_id is None:
                raise

            return await self._send_text_to_topic_raw(
                chat_id=chat_id,
                text=message.text or "",
                message_thread_id=message_thread_id,
            )

    async def _send_text_to_topic_raw(
            self,
            chat_id: str | int,
            text: str,
            message_thread_id: int,
        ) -> MiraTelegramSentMessage:
            client = self._require_client()

            try:
                from pyrogram.raw import functions  # type: ignore
            except ImportError as exc:
                raise RuntimeError("Pyrogram raw API is not available") from exc

            peer = await client.resolve_peer(chat_id)
            random_id = self._build_raw_random_id()

            try:
                result = await client.invoke(
                    functions.messages.SendMessage(
                        peer=peer,
                        message=text,
                        random_id=random_id,
                        no_webpage=True,
                        reply_to_msg_id=message_thread_id,
                        top_msg_id=message_thread_id,
                    )
                )
            except TypeError:
                result = await client.invoke(
                    functions.messages.SendMessage(
                        peer=peer,
                        message=text,
                        random_id=random_id,
                        no_webpage=True,
                        reply_to_msg_id=message_thread_id,
                    )
                )

            message_id = self._extract_raw_sent_message_id(
                result=result,
                random_id=random_id,
            )

            return MiraTelegramSentMessage(
                message_id=message_id,
                chat_id=chat_id,
                text=text,
                caption=None,
                message_thread_id=message_thread_id,
                raw_message=result,
            )

    def _build_raw_random_id(self) -> int:
        client = self._require_client()
        rnd_id = getattr(client, "rnd_id", None)

        if callable(rnd_id):
            value = rnd_id()
            if isinstance(value, int):
                return value

        return random.getrandbits(63)

    def _extract_raw_sent_message_id(
        self,
        result: Any,
        random_id: int,
    ) -> int | None:
        updates = getattr(result, "updates", None)

        if not isinstance(updates, list):
            return None

        for update in updates:
            update_random_id = getattr(update, "random_id", None)
            update_message_id = getattr(update, "id", None)

            if update_random_id == random_id and isinstance(update_message_id, int):
                return update_message_id

        for update in updates:
            message = getattr(update, "message", None)
            message_id = getattr(message, "id", None)

            if isinstance(message_id, int):
                return message_id

        return None

    def _is_unsupported_message_thread_error(
        self,
        error: TypeError,
    ) -> bool:
        message = str(error).lower()

        return (
            "message_thread_id" in message
            and "unexpected keyword" in message
        )

    async def _send_single_media(
        self,
        message: MiraTelegramOutgoingMessage,
        chat_id: str | int,
        message_thread_id: int | None,
    ) -> MiraTelegramSentMessage:
        if not message.attachments:
            return await self._send_text(
                message=message,
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )

        attachment = message.attachments[0]

        with tempfile.TemporaryDirectory(prefix="mira_telegram_") as temp_dir:
            source = self._resolve_attachment_source(attachment, temp_dir)
            raw_message = await self._send_attachment(
                attachment=attachment,
                source=source,
                caption=message.text,
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )

        return self._to_sent_message(
            raw_message=raw_message,
            message_thread_id=message_thread_id,
        )

    async def _send_media_group(
        self,
        message: MiraTelegramOutgoingMessage,
        chat_id: str | int,
        message_thread_id: int | None,
    ) -> list[MiraTelegramSentMessage]:
        if len(message.attachments) < 2:
            return [
                await self._send_single_media(
                    message=message,
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                )
            ]

        with tempfile.TemporaryDirectory(prefix="mira_telegram_") as temp_dir:
            input_media = [
                self._build_input_media(
                    attachment=attachment,
                    source=self._resolve_attachment_source(attachment, temp_dir),
                    caption=message.text if index == 0 else None,
                )
                for index, attachment in enumerate(message.attachments)
            ]

            send_kwargs: dict[str, Any] = {
                "chat_id": chat_id,
                "media": input_media,
            }

            if message_thread_id is not None:
                send_kwargs["message_thread_id"] = message_thread_id

            raw_messages = await self._require_client().send_media_group(**send_kwargs)

        return [
            self._to_sent_message(
                raw_message=raw_message,
                message_thread_id=message_thread_id,
            )
            for raw_message in raw_messages
        ]

    async def _send_attachment(
        self,
        attachment: MiraTelegramAttachment,
        source: str,
        caption: str | None,
        chat_id: str | int,
        message_thread_id: int | None,
    ) -> Any:
        client = self._require_client()

        common_kwargs: dict[str, Any] = {
            "chat_id": chat_id,
            "caption": caption,
        }

        if message_thread_id is not None:
            common_kwargs["message_thread_id"] = message_thread_id

        try:
            if attachment.kind == MiraTelegramAttachmentKind.PHOTO:
                return await client.send_photo(
                    photo=source,
                    **common_kwargs,
                )

            if attachment.kind == MiraTelegramAttachmentKind.VIDEO:
                return await client.send_video(
                    video=source,
                    **common_kwargs,
                )

            if attachment.kind == MiraTelegramAttachmentKind.AUDIO:
                return await client.send_audio(
                    audio=source,
                    **common_kwargs,
                )

            if attachment.kind == MiraTelegramAttachmentKind.VOICE:
                return await client.send_voice(
                    voice=source,
                    **common_kwargs,
                )

            if attachment.kind == MiraTelegramAttachmentKind.ANIMATION:
                return await client.send_animation(
                    animation=source,
                    **common_kwargs,
                )

            return await client.send_document(
                document=source,
                file_name=attachment.filename,
                **common_kwargs,
            )
        except TypeError as exc:
            if not self._is_unsupported_message_thread_error(exc):
                raise

            if message_thread_id is None:
                raise

            if attachment.kind not in {
                MiraTelegramAttachmentKind.DOCUMENT,
                MiraTelegramAttachmentKind.TEXT_FILE,
            }:
                raise

            return await self._send_document_to_topic_raw(
                chat_id=chat_id,
                source=source,
                caption=caption or "",
                filename=attachment.filename,
                mime_type=attachment.mime_type,
                message_thread_id=message_thread_id,
            )

    async def _send_document_to_topic_raw(
        self,
        chat_id: str | int,
        source: str,
        caption: str,
        filename: str | None,
        mime_type: str | None,
        message_thread_id: int,
    ) -> MiraTelegramSentMessage:
        client = self._require_client()

        try:
            from pyrogram.raw import functions, types  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Pyrogram raw API is not available") from exc

        peer = await client.resolve_peer(chat_id)
        random_id = self._build_raw_random_id()

        uploaded_file = await client.save_file(source)
        raw_filename = filename or Path(source).name or "attachment.txt"
        raw_mime_type = mime_type or self._guess_document_mime_type(raw_filename)

        media = self._build_raw_uploaded_document_media(
            types=types,
            uploaded_file=uploaded_file,
            filename=raw_filename,
            mime_type=raw_mime_type,
        )

        try:
            result = await client.invoke(
                functions.messages.SendMedia(
                    peer=peer,
                    media=media,
                    message=caption,
                    random_id=random_id,
                    reply_to_msg_id=message_thread_id,
                    top_msg_id=message_thread_id,
                )
            )
        except TypeError:
            result = await client.invoke(
                functions.messages.SendMedia(
                    peer=peer,
                    media=media,
                    message=caption,
                    random_id=random_id,
                    reply_to_msg_id=message_thread_id,
                )
            )

        message_id = self._extract_raw_sent_message_id(
            result=result,
            random_id=random_id,
        )

        return MiraTelegramSentMessage(
            message_id=message_id,
            chat_id=chat_id,
            text=None,
            caption=caption,
            message_thread_id=message_thread_id,
            raw_message=result,
        )

    def _build_raw_uploaded_document_media(
        self,
        types: Any,
        uploaded_file: Any,
        filename: str,
        mime_type: str,
    ) -> Any:
        attributes = [
            types.DocumentAttributeFilename(
                file_name=filename,
            )
        ]

        try:
            return types.InputMediaUploadedDocument(
                file=uploaded_file,
                mime_type=mime_type,
                attributes=attributes,
                force_file=True,
            )
        except TypeError:
            return types.InputMediaUploadedDocument(
                file=uploaded_file,
                mime_type=mime_type,
                attributes=attributes,
            )

    def _guess_document_mime_type(
        self,
        filename: str,
    ) -> str:
        suffix = Path(filename).suffix.lower()

        if suffix == ".txt":
            return "text/plain"

        if suffix == ".json":
            return "application/json"

        if suffix == ".pdf":
            return "application/pdf"

        if suffix == ".csv":
            return "text/csv"

        return "application/octet-stream"
    

    def _build_input_media(
        self,
        attachment: MiraTelegramAttachment,
        source: str,
        caption: str | None,
    ) -> Any:
        from pyrogram.types import (  # type: ignore
            InputMediaAudio,
            InputMediaDocument,
            InputMediaPhoto,
            InputMediaVideo,
        )

        safe_caption = caption or ""

        if attachment.kind == MiraTelegramAttachmentKind.PHOTO:
            return InputMediaPhoto(
                media=source,
                caption=safe_caption,
            )

        if attachment.kind == MiraTelegramAttachmentKind.VIDEO:
            return InputMediaVideo(
                media=source,
                caption=safe_caption,
            )

        if attachment.kind == MiraTelegramAttachmentKind.AUDIO:
            return InputMediaAudio(
                media=source,
                caption=safe_caption,
            )

        if attachment.kind == MiraTelegramAttachmentKind.DOCUMENT:
            return InputMediaDocument(
                media=source,
                caption=safe_caption,
            )

        raise ValueError(
            f"Attachment kind {attachment.kind.value!r} cannot be sent in media group"
        )

    def _resolve_attachment_source(
        self,
        attachment: MiraTelegramAttachment,
        temp_dir: str,
    ) -> str:
        if attachment.text_file is not None:
            filename = self._safe_filename(attachment.filename or "mira_request.txt")
            path = Path(temp_dir) / filename
            path.write_text(attachment.text_file.content, encoding="utf-8")
            return str(path)

        if attachment.source:
            return attachment.source

        raise ValueError(
            f"Attachment {attachment.kind.value!r} has no source or text file"
        )

    def _safe_filename(self, filename: str) -> str:
        value = filename.strip().replace("\\", "_").replace("/", "_")

        if not value:
            return "file"

        return value

    def _normalize_username(self, value: str | int | None) -> str:
        if not isinstance(value, str):
            return ""

        return value.strip().lower().removeprefix("@")

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("MiraTelegramClient is not started")

        return self._client

    def _to_sent_message(
        self,
        raw_message: Any,
        message_thread_id: int | None = None,
    ) -> MiraTelegramSentMessage:
        chat = getattr(raw_message, "chat", None)
        chat_id = getattr(chat, "id", None)

        raw_thread_id = getattr(raw_message, "message_thread_id", None)
        resolved_thread_id = (
            raw_thread_id
            if isinstance(raw_thread_id, int)
            else message_thread_id
        )

        return MiraTelegramSentMessage(
            message_id=getattr(raw_message, "id", None),
            chat_id=chat_id,
            text=getattr(raw_message, "text", None),
            caption=getattr(raw_message, "caption", None),
            message_thread_id=resolved_thread_id,
            raw_message=raw_message,
        )
        

