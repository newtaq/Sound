import re
from typing import Any

from app.application.ai_debug import AIVisualDebugSink
from app.application.contracts import (
    AIRequest,
    AIResponse,
    AIStreamChunk,
    AIStreamEventType,
)
from app.infrastructure.telegram_debug.config import (
    TelegramVisualDebugConfig,
    load_telegram_visual_debug_config,
)
from app.infrastructure.telegram_debug.models import (
    TelegramDebugMessage,
    TelegramDebugMessageKind,
)
from app.infrastructure.telegram_debug.sink import TelegramVisualDebugSink


class TelegramAIVisualDebugSink(AIVisualDebugSink):
    def __init__(
        self,
        config: TelegramVisualDebugConfig | None = None,
        telegram_sink: TelegramVisualDebugSink | None = None,
    ) -> None:
        self._config = config or load_telegram_visual_debug_config()
        self._telegram_sink = telegram_sink or TelegramVisualDebugSink(
            config=self._config,
        )

    def emit_request(
        self,
        request: AIRequest,
        provider_name: str | None = None,
    ) -> None:
        if self._should_skip_poster_agent_ai_message(request.metadata):
            return

        event_title = self._read_event_title(request.metadata) or self._extract_event_title(
            request.text,
        )
        event_date = self._read_event_date(request.metadata) or self._extract_event_date(
            request.text,
        )

        self._telegram_sink.emit_background(
            TelegramDebugMessage(
                kind=TelegramDebugMessageKind.REQUEST,
                session_id=request.session_id,
                request_id=request.request_id,
                provider_name=provider_name or request.provider_name,
                event_title=event_title,
                text=request.text,
                metadata={
                    **self._compact_metadata(request.metadata),
                    "event_title": event_title,
                    "event_date": event_date,
                    "mode": request.mode.value,
                    "response_format": request.response_format,
                    "media_count": len(request.media),
                    "text_file_count": len(request.text_files),
                    "history_count": len(request.history),
                    "instructions_length": len(request.instructions or ""),
                },
            )
        )

    def emit_response(
        self,
        request: AIRequest,
        response: AIResponse,
    ) -> None:
        if self._should_skip_poster_agent_ai_message(
            {
                **request.metadata,
                **response.metadata,
            }
        ):
            return

        kind = (
            TelegramDebugMessageKind.RESPONSE
            if response.error is None
            else TelegramDebugMessageKind.ERROR
        )

        self._telegram_sink.emit_background(
            TelegramDebugMessage(
                kind=kind,
                session_id=response.session_id or request.session_id,
                request_id=response.request_id or request.request_id,
                provider_name=response.provider_name or request.provider_name,
                event_title=self._read_event_title(
                    {
                        **request.metadata,
                        **response.metadata,
                    }
                ),
                text=self._build_response_debug_text(
                    request=request,
                    response=response,
                ),
                metadata=self._build_response_debug_metadata(
                    request=request,
                    response=response,
                ),
            )
        )

    def _should_skip_poster_agent_ai_message(
        self,
        metadata: dict[str, Any],
    ) -> bool:
        return metadata.get("poster_agent_pipeline") is True

    def _build_response_debug_text(
        self,
        request: AIRequest,
        response: AIResponse,
    ) -> str:
        if response.error:
            return response.error

        if self._should_compact_poster_agent_response(
            request=request,
            response=response,
        ):
            return "Ответ verifier-agent получен."

        return response.text

    def _build_response_debug_metadata(
        self,
        request: AIRequest,
        response: AIResponse,
    ) -> dict[str, Any]:
        metadata = {
            **self._compact_metadata(response.metadata),
            "status": response.status.value,
            "error": response.error,
            "attachment_count": len(response.attachments),
            "raw_message_count": len(response.raw_messages),
        }

        if self._should_compact_poster_agent_response(
            request=request,
            response=response,
        ):
            metadata["raw_response_text"] = self._compact_debug_text(
                response.text,
                limit=1800,
            )

        return metadata

    def _should_compact_poster_agent_response(
        self,
        request: AIRequest,
        response: AIResponse,
    ) -> bool:
        metadata = {
            **request.metadata,
            **response.metadata,
        }

        if metadata.get("poster_agent_pipeline") is not True:
            return False

        if metadata.get("structured_verification") is not True:
            return False

        if response.error:
            return False

        return self._looks_like_json_response(response.text)

    def _compact_debug_text(
        self,
        text: str,
        limit: int,
    ) -> str:
        value = text.strip()

        if len(value) <= limit:
            return value

        return value[: limit - 24].rstrip() + " ...[truncated]"

    def _looks_like_json_response(
        self,
        text: str,
    ) -> bool:
        value = text.strip()

        if not value:
            return False

        if value.startswith("{") and value.endswith("}"):
            return True

        if value.startswith("```json"):
            return True

        if value.startswith("```") and "{" in value[:20]:
            return True

        return False

    def emit_stream_chunk(
        self,
        request: AIRequest,
        chunk: AIStreamChunk,
    ) -> None:
        if self._should_skip_poster_agent_ai_message(
            {
                **request.metadata,
                **chunk.metadata,
            }
        ):
            return

        if (
            chunk.event_type == AIStreamEventType.MESSAGE_UPDATED
            and not self._config.include_stream_deltas
        ):
            return

        kind = self._map_stream_kind(chunk.event_type)

        self._telegram_sink.emit_background(
            TelegramDebugMessage(
                kind=kind,
                session_id=chunk.session_id or request.session_id,
                request_id=chunk.request_id or request.request_id,
                provider_name=chunk.provider_name or request.provider_name,
                event_title=self._read_event_title(
                    {
                        **request.metadata,
                        **chunk.metadata,
                    }
                ),
                text=chunk.text,
                full_text=chunk.full_text,
                metadata={
                    **self._compact_metadata(chunk.metadata),
                    "stream_event_type": chunk.event_type.value,
                    "error": chunk.error,
                    "attachment_count": len(chunk.attachments),
                },
            )
        )

    def _map_stream_kind(
        self,
        event_type: AIStreamEventType,
    ) -> TelegramDebugMessageKind:
        if event_type == AIStreamEventType.STARTED:
            return TelegramDebugMessageKind.STREAM_STARTED

        if event_type == AIStreamEventType.MESSAGE_UPDATED:
            return TelegramDebugMessageKind.STREAM_DELTA

        if event_type in {
            AIStreamEventType.MESSAGE_FINISHED,
            AIStreamEventType.FINISHED,
        }:
            return TelegramDebugMessageKind.STREAM_FINISHED

        if event_type == AIStreamEventType.ERROR:
            return TelegramDebugMessageKind.ERROR

        return TelegramDebugMessageKind.INFO

    def _extract_event_title(
        self,
        text: str,
    ) -> str | None:
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        for line in lines:
            value = self._extract_labeled_value(
                line,
                labels=(
                    "Название",
                    "Название события",
                    "Событие",
                    "Афиша",
                    "Title",
                    "Event",
                    "Event title",
                ),
            )

            if value:
                return self._clean_event_title(value)

        for line in lines:
            if self._is_bad_title_candidate(line):
                continue

            cleaned = self._clean_event_title(line)

            if cleaned:
                return cleaned

        return None

    def _extract_event_date(
        self,
        text: str,
    ) -> str | None:
        iso_match = re.search(
            r"\b20\d{2}-\d{2}-\d{2}\b",
            text,
        )

        if iso_match:
            return iso_match.group(0)

        labeled_patterns = [
            r"(?im)^\s*(?:Дата|Когда|Date)\s*:\s*(.+?)\s*$",
            r"(?im)^\s*(?:Даты и города|Даты|Dates)\s*:\s*(.+?)\s*$",
        ]

        for pattern in labeled_patterns:
            match = re.search(pattern, text)

            if match:
                value = self._clean_date_value(match.group(1))

                if value:
                    return value

        russian_date = re.search(
            r"\b\d{1,2}\s+"
            r"(?:января|февраля|марта|апреля|мая|июня|июля|"
            r"августа|сентября|октября|ноября|декабря)"
            r"(?:\s+20\d{2})?\b",
            text,
            flags=re.IGNORECASE,
        )

        if russian_date:
            return russian_date.group(0)

        dotted_date = re.search(
            r"\b\d{1,2}\.\d{1,2}(?:\.\d{2,4})?\b",
            text,
        )

        if dotted_date:
            return dotted_date.group(0)

        return None

    def _extract_labeled_value(
        self,
        line: str,
        labels: tuple[str, ...],
    ) -> str | None:
        for label in labels:
            prefix = f"{label}:"

            if line.lower().startswith(prefix.lower()):
                value = line[len(prefix):].strip()

                if value:
                    return value

        return None

    def _clean_event_title(
        self,
        value: str,
    ) -> str | None:
        cleaned = " ".join(value.strip().split())
        cleaned = cleaned.strip("`*_-: ")

        if not cleaned:
            return None

        if self._is_bad_title_candidate(cleaned):
            return None

        if len(cleaned) > 80:
            cleaned = cleaned[:79].rstrip() + ""

        return cleaned

    def _clean_date_value(
        self,
        value: str,
    ) -> str | None:
        cleaned = " ".join(value.strip().split())
        cleaned = cleaned.strip("`*_-: ")

        if not cleaned:
            return None

        if len(cleaned) > 40:
            cleaned = cleaned[:39].rstrip() + ""

        return cleaned

    def _is_bad_title_candidate(
        self,
        line: str,
    ) -> bool:
        lowered = line.lower().strip()

        if not lowered:
            return True

        bad_prefixes = (
            "из этих данных",
            "нужно вывести",
            "если включ",
            "ответь",
            "ссылки",
            "билеты",
            "контекст",
            "запрос",
            "метаданные",
            "metadata",
            "http://",
            "https://",
            "- http://",
            "- https://",
        )

        if lowered.startswith(bad_prefixes):
            return True

        if len(line) > 120:
            return True

        return False

    def _read_event_date(
        self,
        metadata: dict[str, Any],
    ) -> str | None:
        for key in (
            "event_date",
            "date",
            "poster_date",
            "started_at",
            "start_date",
        ):
            value = metadata.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

        return None

    def _read_event_title(
        self,
        metadata: dict[str, Any],
    ) -> str | None:
        for key in (
            "event_title",
            "poster_title",
            "title",
            "event_name",
            "artist",
        ):
            value = metadata.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

        return None

    def _compact_metadata(
        self,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, value in metadata.items():
            result[str(key)] = self._to_jsonable(value)

        return result

    def _to_jsonable(
        self,
        value: Any,
    ) -> Any:
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value[:20]]

        if isinstance(value, tuple):
            return [self._to_jsonable(item) for item in value[:20]]

        if isinstance(value, dict):
            return {
                str(key): self._to_jsonable(item)
                for key, item in list(value.items())[:50]
            }

        if hasattr(value, "value"):
            return value.value

        return str(value)
