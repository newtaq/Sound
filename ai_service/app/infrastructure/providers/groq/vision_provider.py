import base64
from pathlib import Path
from collections.abc import AsyncIterator
from typing import Any

from app.application.contracts import (
    AIMedia,
    AIMessageRole,
    AIProviderCapabilities,
    AIProviderLimits,
    AIRequest,
    AIStreamChunk,
    AIStreamEventType,
)
from app.infrastructure.providers.groq.config import GroqProviderConfig
from app.infrastructure.providers.groq.provider import GroqProvider


class GroqVisionProvider(GroqProvider):
    def __init__(
        self,
        config: GroqProviderConfig | None = None,
    ) -> None:
        super().__init__(config=config)

    @property
    def name(self) -> str:
        return "groq_vision"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(
            can_stream=True,
            can_stream_message_edits=False,
            can_analyze_images=True,
            can_search_web_natively=False,
            can_use_files=False,
            max_media_count=5,
            max_text_length=None,
        )

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=None,
            max_media_count=5,
            max_media_caption_length=None,
            max_message_count_per_request=None,
            one_active_request_per_session=False,
            send_large_text_as_file=False,
            request_timeout_seconds=self._config.timeout_seconds,
            retry_count=self._config.max_retries,
            retry_delay_seconds=self._config.retry_delay_seconds,
        )

    def _get_model(self) -> str:
        return self._config.vision_model

    async def generate(
        self,
        request: AIRequest,
    ):
        if not request.media:
            return await super().generate(request)

        return await self._generate_vision(request)

    async def _stream(
        self,
        request: AIRequest,
    ) -> AsyncIterator[AIStreamChunk]:
        if not request.media:
            async for chunk in super()._stream(request):
                yield chunk
            return

        model = self._get_model()
        keys = self._config.get_all_api_keys()

        if not keys:
            yield AIStreamChunk(
                event_type=AIStreamEventType.ERROR,
                provider_name=self.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error="GROQ_API_KEYS is not configured",
                metadata={
                    "provider": self.name,
                    "model": model,
                    "key_count": 0,
                    "media_count": len(request.media),
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                    "stream_transport": "groq_vision_native_stream",
                },
            )
            return

        yield AIStreamChunk(
            event_type=AIStreamEventType.STARTED,
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
            metadata={
                "provider": self.name,
                "model": model,
                "key_count": len(keys),
                "media_count": len(request.media),
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_vision_native_stream",
            },
        )

        start_index = self._select_start_key_index(len(keys))
        errors: list[str] = []

        for offset in range(len(keys)):
            key_index = (start_index + offset) % len(keys)

            try:
                async for chunk in self._stream_vision_with_key(
                    request=request,
                    key_index=key_index,
                ):
                    yield chunk
                return
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                errors.append(f"key[{key_index}]: {error_text}")

                if not self._should_try_next_key(exc):
                    break

        yield AIStreamChunk(
            event_type=AIStreamEventType.ERROR,
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
            error=f"{self.name} provider stream failed with all available API keys",
            metadata={
                "provider": self.name,
                "model": model,
                "key_count": len(keys),
                "media_count": len(request.media),
                "key_errors": errors,
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_vision_native_stream",
            },
        )

    async def _stream_vision_with_key(
        self,
        request: AIRequest,
        key_index: int,
    ) -> AsyncIterator[AIStreamChunk]:
        client = self._get_client(key_index)
        messages = self._build_vision_messages(request)
        model = self._get_model()
        full_text = ""
        finish_reason: str | None = None

        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self._config.temperature,
            max_completion_tokens=self._config.max_completion_tokens,
            stream=True,
        )

        for item in stream:
            delta = self._extract_stream_delta(item)
            current_finish_reason = self._extract_finish_reason(item)

            if current_finish_reason is not None:
                finish_reason = current_finish_reason

            if not delta:
                continue

            full_text += delta

            yield AIStreamChunk(
                event_type=AIStreamEventType.MESSAGE_UPDATED,
                text=delta,
                full_text=full_text,
                provider_name=self.name,
                session_id=request.session_id,
                request_id=request.request_id,
                metadata={
                    "provider": self.name,
                    "model": model,
                    "key_index": key_index,
                    "key_count": len(self._config.get_all_api_keys()),
                    "media_count": len(request.media),
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                    "stream_transport": "groq_vision_native_stream",
                },
            )

        yield AIStreamChunk(
            event_type=AIStreamEventType.FINISHED,
            full_text=full_text,
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
            metadata={
                "provider": self.name,
                "model": model,
                "key_index": key_index,
                "key_count": len(self._config.get_all_api_keys()),
                "media_count": len(request.media),
                "finish_reason": finish_reason,
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_vision_native_stream",
            },
        )

    async def _generate_vision(
        self,
        request: AIRequest,
    ):
        keys = self._config.get_all_api_keys()

        if not keys:
            from app.application.contracts import AIResponse, AIResponseStatus

            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=self.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error="GROQ_API_KEYS is not configured",
                metadata={
                    "provider": self.name,
                    "model": self._get_model(),
                    "key_count": 0,
                },
            )

        start_index = self._select_start_key_index(len(keys))
        errors: list[str] = []

        for offset in range(len(keys)):
            key_index = (start_index + offset) % len(keys)

            try:
                return await self._generate_vision_with_key(
                    request=request,
                    key_index=key_index,
                )
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                errors.append(f"key[{key_index}]: {error_text}")

                if not self._should_try_next_key(exc):
                    break

        from app.application.contracts import AIResponse, AIResponseStatus

        return AIResponse(
            status=AIResponseStatus.ERROR,
            text="",
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
            error=f"{self.name} provider failed with all available API keys",
            metadata={
                "provider": self.name,
                "model": self._get_model(),
                "key_count": len(keys),
                "key_errors": errors,
            },
        )

    async def _generate_vision_with_key(
        self,
        request: AIRequest,
        key_index: int,
    ):
        from app.application.contracts import AIResponse, AIResponseStatus

        client = self._get_client(key_index)
        messages = self._build_vision_messages(request)
        model = self._get_model()

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self._config.temperature,
            max_completion_tokens=self._config.max_completion_tokens,
        )

        text = self._extract_text(completion)

        return AIResponse(
            status=AIResponseStatus.OK,
            text=text,
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
            raw_messages=[text],
            metadata={
                "provider": self.name,
                "model": model,
                "key_index": key_index,
                "key_count": len(self._config.get_all_api_keys()),
                "media_count": len(request.media),
                "usage": self._extract_usage(completion),
                "finish_reason": self._extract_finish_reason(completion),
            },
        )

    def _build_vision_messages(
        self,
        request: AIRequest,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        system_parts: list[str] = []

        if request.instructions:
            system_parts.append(request.instructions.strip())

        if request.response_format:
            system_parts.append(f"Response format: {request.response_format}")

        if system_parts:
            messages.append(
                {
                    "role": "system",
                    "content": "\n\n".join(system_parts),
                }
            )

        for history_message in request.history:
            role = self._map_role(history_message.role)
            content = history_message.content.strip()

            if not content:
                continue

            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": request.text.strip(),
            }
        ]

        for media in request.media:
            image_url = self._build_image_url(media)

            if image_url is None:
                continue

            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                    },
                }
            )

        messages.append(
            {
                "role": "user",
                "content": content,
            }
        )

        return messages

    def _build_image_url(
        self,
        media: AIMedia,
    ) -> str | None:
        if media.url:
            return media.url

        if media.path:
            return self._build_data_url(
                path=media.path,
                mime_type=media.mime_type,
            )

        return None

    def _build_data_url(
        self,
        path: str,
        mime_type: str | None,
    ) -> str:
        file_path = Path(path)
        raw = file_path.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        resolved_mime_type = mime_type or self._guess_image_mime_type(file_path)

        return f"data:{resolved_mime_type};base64,{encoded}"

    def _guess_image_mime_type(
        self,
        path: Path,
    ) -> str:
        suffix = path.suffix.lower()

        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"

        if suffix == ".png":
            return "image/png"

        if suffix == ".webp":
            return "image/webp"

        if suffix == ".gif":
            return "image/gif"

        return "application/octet-stream"
    

