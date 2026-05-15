from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.application.contracts import (
    AIMedia,
    AIMediaType,
    AIMessageRole,
    AIRequest,
    AITextFile,
)
from app.infrastructure.providers.mira.config import MiraTelegramProviderConfig


class MiraTelegramAttachmentKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    ANIMATION = "animation"
    DOCUMENT = "document"
    TEXT_FILE = "text_file"


class MiraTelegramMessageKind(StrEnum):
    TEXT = "text"
    SINGLE_MEDIA = "single_media"
    MEDIA_GROUP = "media_group"


@dataclass(slots=True)
class MiraTelegramAttachment:
    kind: MiraTelegramAttachmentKind
    source: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    text_file: AITextFile | None = None
    original_media: AIMedia | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MiraTelegramOutgoingMessage:
    kind: MiraTelegramMessageKind = MiraTelegramMessageKind.TEXT
    text: str | None = None
    attachments: list[MiraTelegramAttachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class MiraTelegramRequestPacker:
    def __init__(self, config: MiraTelegramProviderConfig | None = None) -> None:
        self._config = config or MiraTelegramProviderConfig()

    def build_messages(self, request: AIRequest) -> list[MiraTelegramOutgoingMessage]:
        prompt_text = self._with_trigger_prefix(self._build_prompt_text(request))

        text_file_attachments = self._build_text_file_attachments(request.text_files)
        media_attachments = self._build_media_attachments(request.media)

        attachments = [
            *text_file_attachments,
            *media_attachments,
        ]

        if not attachments:
            return [self._pack_text_only(prompt_text)]

        attachment_messages = self._pack_attachments_without_trigger(attachments)

        if len(prompt_text) <= self._config.max_caption_length:
            return self._put_prompt_on_last_message(
                messages=attachment_messages,
                prompt_text=prompt_text,
            )

        prompt_file_message = self._pack_prompt_as_final_text_file(prompt_text)
        return [
            *attachment_messages,
            prompt_file_message,
        ]

    def _pack_text_only(self, prompt_text: str) -> MiraTelegramOutgoingMessage:
        if len(prompt_text) <= self._config.max_text_message_length:
            return MiraTelegramOutgoingMessage(
                kind=MiraTelegramMessageKind.TEXT,
                text=prompt_text,
                metadata={
                    "telegram_message_role": "prompt",
                    "trigger_position": "only_message",
                },
            )

        return self._pack_prompt_as_final_text_file(prompt_text)

    def _pack_prompt_as_final_text_file(
        self,
        prompt_text: str,
    ) -> MiraTelegramOutgoingMessage:
        filename = "full_user_request_for_mira.txt"

        text_file = AITextFile(
            filename=filename,
            content=prompt_text,
        )

        return MiraTelegramOutgoingMessage(
            kind=MiraTelegramMessageKind.SINGLE_MEDIA,
            text=self._with_trigger_prefix(
                f"Полный текст запроса приложен в файле {filename}. "
                "Прочитай этот файл полностью и выполни задачу. "
                "Если перед этим были отправлены медиа или другие файлы, учти их тоже. "
                "Не создавай новые медиафайлы, изображения, голосовые, музыку, видео или GIF."
            ),
            attachments=[
                MiraTelegramAttachment(
                    kind=MiraTelegramAttachmentKind.TEXT_FILE,
                    filename=text_file.filename,
                    mime_type=text_file.mime_type,
                    text_file=text_file,
                )
            ],
            metadata={
                "telegram_message_role": "prompt_text_file",
                "large_text_as_file": True,
                "trigger_position": "final_message",
                "filename": filename,
            },
        )

    def _pack_attachments_without_trigger(
        self,
        attachments: list[MiraTelegramAttachment],
    ) -> list[MiraTelegramOutgoingMessage]:
        photo_video: list[MiraTelegramAttachment] = []
        audios: list[MiraTelegramAttachment] = []
        documents: list[MiraTelegramAttachment] = []
        singles: list[MiraTelegramAttachment] = []

        for attachment in attachments:
            if attachment.kind in {
                MiraTelegramAttachmentKind.PHOTO,
                MiraTelegramAttachmentKind.VIDEO,
            }:
                photo_video.append(attachment)
            elif attachment.kind == MiraTelegramAttachmentKind.AUDIO:
                audios.append(attachment)
            elif attachment.kind in {
                MiraTelegramAttachmentKind.DOCUMENT,
                MiraTelegramAttachmentKind.TEXT_FILE,
            }:
                documents.append(attachment)
            else:
                singles.append(attachment)

        messages: list[MiraTelegramOutgoingMessage] = []

        for group_name, group in [
            ("photo_video", photo_video),
            ("audio", audios),
            ("document", documents),
        ]:
            messages.extend(
                self._pack_compatible_media_group(
                    group_name=group_name,
                    attachments=group,
                )
            )

        for attachment in singles:
            messages.append(
                MiraTelegramOutgoingMessage(
                    kind=MiraTelegramMessageKind.SINGLE_MEDIA,
                    attachments=[attachment],
                    metadata={
                        "telegram_message_role": "single_media",
                        "attachment_kind": attachment.kind.value,
                        "trigger_position": "none",
                    },
                )
            )

        return messages

    def _pack_compatible_media_group(
        self,
        group_name: str,
        attachments: list[MiraTelegramAttachment],
    ) -> list[MiraTelegramOutgoingMessage]:
        if not attachments:
            return []

        if len(attachments) == 1:
            return [
                MiraTelegramOutgoingMessage(
                    kind=MiraTelegramMessageKind.SINGLE_MEDIA,
                    attachments=attachments,
                    metadata={
                        "telegram_message_role": "single_media",
                        "media_group_type": group_name,
                        "trigger_position": "none",
                    },
                )
            ]

        chunks = self._split_chunks(attachments, self._config.max_media_count)
        messages: list[MiraTelegramOutgoingMessage] = []

        for chunk_index, chunk in enumerate(chunks):
            messages.append(
                MiraTelegramOutgoingMessage(
                    kind=MiraTelegramMessageKind.MEDIA_GROUP,
                    attachments=chunk,
                    metadata={
                        "telegram_message_role": "media_group",
                        "media_group_type": group_name,
                        "media_group_index": chunk_index + 1,
                        "media_group_total": len(chunks),
                        "trigger_position": "none",
                    },
                )
            )

        return messages

    def _put_prompt_on_last_message(
        self,
        messages: list[MiraTelegramOutgoingMessage],
        prompt_text: str,
    ) -> list[MiraTelegramOutgoingMessage]:
        if not messages:
            return [self._pack_text_only(prompt_text)]

        last_message = messages[-1]
        last_message.text = prompt_text
        last_message.metadata = {
            **last_message.metadata,
            "telegram_message_role": "prompt_attachment",
            "trigger_position": "final_message",
        }

        return messages

    def _split_chunks(
        self,
        items: list[MiraTelegramAttachment],
        size: int,
    ) -> list[list[MiraTelegramAttachment]]:
        return [
            items[index:index + size]
            for index in range(0, len(items), size)
        ]

    def _build_prompt_text(self, request: AIRequest) -> str:
        blocks: list[str] = []

        blocks.append(
            "\n".join(
                [
                    "Контекст интеграции:",
                    "Сейчас используется текстовый режим ответа.",
                    "Создание новых изображений, голосовых сообщений, музыки, видео, GIF, стикеров и других медиафайлов в этой интеграции не требуется.",
                    "Если в запросе уже приложены файлы или медиа, их можно использовать как входные данные для анализа.",
                    "Если задача подразумевает создание нового медиафайла, достаточно дать обычный текстовый ответ.",
                ]
            )
        )

        if request.instructions:
            blocks.append(f"Инструкция:\n{request.instructions.strip()}")

        history_text = self._build_history_text(request)
        if history_text:
            blocks.append(f"История диалога:\n{history_text}")

        if request.text_files:
            filenames = ", ".join(text_file.filename for text_file in request.text_files)
            blocks.append(f"Текстовые вложения: {filenames}")

        if request.media:
            media_names = [
                media.filename or media.path or media.url or media.media_id or media.media_type.value
                for media in request.media
            ]
            blocks.append(f"Медиа-вложения для анализа: {', '.join(media_names)}")

        blocks.append(f"Запрос:\n{request.text.strip()}")

        if request.response_format:
            blocks.append(f"Формат ответа: {request.response_format}")

        return "\n\n".join(block for block in blocks if block.strip())

    def _build_history_text(self, request: AIRequest) -> str:
        if not request.history:
            return ""

        lines: list[str] = []

        for message in request.history:
            role = self._format_role(message.role)
            content = message.content.strip()

            if content:
                lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _format_role(self, role: AIMessageRole) -> str:
        if role == AIMessageRole.SYSTEM:
            return "system"

        if role == AIMessageRole.ASSISTANT:
            return "assistant"

        if role == AIMessageRole.TOOL:
            return "tool"

        return "user"

    def _with_trigger_prefix(self, text: str) -> str:
        stripped_text = text.strip()
        prefix = self._config.trigger_prefix.strip()

        if not prefix:
            return stripped_text

        if stripped_text.lower().startswith(prefix.lower()):
            return stripped_text

        return f"{prefix} {stripped_text}"

    def _build_text_file_attachments(
        self,
        text_files: list[AITextFile],
    ) -> list[MiraTelegramAttachment]:
        return [
            MiraTelegramAttachment(
                kind=MiraTelegramAttachmentKind.TEXT_FILE,
                filename=text_file.filename,
                mime_type=text_file.mime_type,
                text_file=text_file,
            )
            for text_file in text_files
        ]

    def _build_media_attachments(
        self,
        media_items: list[AIMedia],
    ) -> list[MiraTelegramAttachment]:
        return [self._build_media_attachment(media) for media in media_items]

    def _build_media_attachment(self, media: AIMedia) -> MiraTelegramAttachment:
        kind = self._resolve_media_kind(media)

        return MiraTelegramAttachment(
            kind=kind,
            source=self._resolve_media_source(media),
            filename=media.filename,
            mime_type=media.mime_type,
            original_media=media,
            metadata=dict(media.metadata),
        )

    def _resolve_media_kind(self, media: AIMedia) -> MiraTelegramAttachmentKind:
        if self._is_voice(media):
            return MiraTelegramAttachmentKind.VOICE

        if self._is_animation(media):
            return MiraTelegramAttachmentKind.ANIMATION

        if media.media_type == AIMediaType.IMAGE:
            return MiraTelegramAttachmentKind.PHOTO

        if media.media_type == AIMediaType.VIDEO:
            return MiraTelegramAttachmentKind.VIDEO

        if media.media_type == AIMediaType.AUDIO:
            return MiraTelegramAttachmentKind.AUDIO

        return MiraTelegramAttachmentKind.DOCUMENT

    def _is_voice(self, media: AIMedia) -> bool:
        telegram_kind = str(media.metadata.get("telegram_kind", "")).lower()
        send_as = str(media.metadata.get("send_as", "")).lower()

        if telegram_kind == "voice" or send_as == "voice":
            return True

        if media.metadata.get("is_voice") is True:
            return True

        suffix = Path(media.filename or media.path or "").suffix.lower()

        return (
            media.media_type == AIMediaType.AUDIO
            and suffix in {".ogg", ".oga", ".opus"}
            and media.mime_type in {None, "audio/ogg", "audio/oga", "audio/opus"}
        )

    def _is_animation(self, media: AIMedia) -> bool:
        telegram_kind = str(media.metadata.get("telegram_kind", "")).lower()
        send_as = str(media.metadata.get("send_as", "")).lower()

        if telegram_kind in {"animation", "gif"} or send_as in {"animation", "gif"}:
            return True

        suffix = Path(media.filename or media.path or "").suffix.lower()
        mime_type = (media.mime_type or "").lower()

        return suffix == ".gif" or mime_type == "image/gif"

    def _resolve_media_source(self, media: AIMedia) -> str | None:
        return media.path or media.url or media.media_id
    

