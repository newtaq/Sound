from typing import Any, AsyncIterator

from app.application.contracts import (
    AIMessageRole,
    AIProviderCapabilities,
    AIProviderLimits,
    AIProviderStatus,
    AIRequest,
    AIResponse,
    AIResponseStatus,
    AIStreamChunk,
    AIStreamEventType,
    StreamingAIProvider,
)
from app.infrastructure.providers.groq.config import (
    GroqProviderConfig,
    load_groq_provider_config,
)


class GroqProvider(StreamingAIProvider):
    def __init__(
        self,
        config: GroqProviderConfig | None = None,
    ) -> None:
        self._config = config or load_groq_provider_config()
        self._clients: dict[int, Any] = {}
        self._next_key_index = 0

    @property
    def name(self) -> str:
        return "groq"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(
            can_stream=True,
            can_stream_message_edits=False,
            can_analyze_images=False,
            can_search_web_natively=False,
            can_use_files=False,
            max_media_count=0,
            max_text_length=None,
        )

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=None,
            max_media_count=0,
            max_media_caption_length=0,
            max_message_count_per_request=None,
            one_active_request_per_session=False,
            send_large_text_as_file=False,
            request_timeout_seconds=self._config.timeout_seconds,
            retry_count=self._config.max_retries,
            retry_delay_seconds=self._config.retry_delay_seconds,
        )

    @property
    def status(self) -> AIProviderStatus:
        if not self._config.has_api_key:
            return AIProviderStatus(
                available=False,
                reason="GROQ_API_KEYS is not configured",
            )

        return AIProviderStatus(available=True)

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponse:
        if request.media:
            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=self.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error=f"{self.name} provider does not support media in this implementation",
                metadata={
                    "provider": self.name,
                    "model": self._get_model(),
                    "key_count": len(self._config.get_all_api_keys()),
                },
            )

        keys = self._config.get_all_api_keys()

        if not keys:
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
                return await self._generate_with_key(
                    request=request,
                    key_index=key_index,
                )
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                errors.append(f"key[{key_index}]: {error_text}")

                if not self._should_try_next_key(exc):
                    break

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

    def stream(
        self,
        request: AIRequest,
    ) -> AsyncIterator[AIStreamChunk]:
        return self._stream(request)

    async def _stream(
        self,
        request: AIRequest,
    ) -> AsyncIterator[AIStreamChunk]:
        model = self._get_model()

        if request.media:
            yield AIStreamChunk(
                event_type=AIStreamEventType.ERROR,
                provider_name=self.name,
                session_id=request.session_id,
                error=f"{self.name} provider does not support media streaming",
                metadata={
                    "provider": self.name,
                    "model": model,
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                },
            )
            return

        keys = self._config.get_all_api_keys()

        if not keys:
            yield AIStreamChunk(
                event_type=AIStreamEventType.ERROR,
                provider_name=self.name,
                session_id=request.session_id,
                error="GROQ_API_KEYS is not configured",
                metadata={
                    "provider": self.name,
                    "model": model,
                    "key_count": 0,
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                },
            )
            return

        yield AIStreamChunk(
            event_type=AIStreamEventType.STARTED,
            provider_name=self.name,
            session_id=request.session_id,
            metadata={
                "provider": self.name,
                "model": model,
                "key_count": len(keys),
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_native_stream",
            },
        )

        start_index = self._select_start_key_index(len(keys))
        errors: list[str] = []

        for offset in range(len(keys)):
            key_index = (start_index + offset) % len(keys)

            try:
                async for chunk in self._stream_with_key(
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
            error=f"{self.name} provider stream failed with all available API keys",
            metadata={
                "provider": self.name,
                "model": model,
                "key_count": len(keys),
                "key_errors": errors,
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_native_stream",
            },
        )

    async def _stream_with_key(
        self,
        request: AIRequest,
        key_index: int,
    ) -> AsyncIterator[AIStreamChunk]:
        client = self._get_client(key_index)
        messages = self._build_messages(request)
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
                metadata={
                    "provider": self.name,
                    "model": model,
                    "key_index": key_index,
                    "key_count": len(self._config.get_all_api_keys()),
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                    "stream_transport": "groq_native_stream",
                },
            )

        yield AIStreamChunk(
            event_type=AIStreamEventType.FINISHED,
            full_text=full_text,
            provider_name=self.name,
            session_id=request.session_id,
            metadata={
                "provider": self.name,
                "model": model,
                "key_index": key_index,
                "key_count": len(self._config.get_all_api_keys()),
                "finish_reason": finish_reason,
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_native_stream",
            },
        )

    async def _generate_with_key(
        self,
        request: AIRequest,
        key_index: int,
    ) -> AIResponse:
        client = self._get_client(key_index)
        messages = self._build_messages(request)
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
                "usage": self._extract_usage(completion),
                "finish_reason": self._extract_finish_reason(completion),
            },
        )

    def _get_model(self) -> str:
        return self._config.model

    def _get_client(
        self,
        key_index: int,
    ) -> Any:
        if key_index in self._clients:
            return self._clients[key_index]

        keys = self._config.get_all_api_keys()

        if key_index < 0 or key_index >= len(keys):
            raise RuntimeError(f"Groq API key index is out of range: {key_index}")

        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError(
                "Groq SDK is not installed. Install it with: py -m pip install groq"
            ) from exc

        client = Groq(
            api_key=keys[key_index],
            timeout=self._config.timeout_seconds,
        )

        self._clients[key_index] = client

        return client

    def _select_start_key_index(
        self,
        key_count: int,
    ) -> int:
        if key_count <= 1:
            return 0

        strategy = self._config.key_strategy.strip().lower()

        if strategy == "first":
            return 0

        index = self._next_key_index % key_count
        self._next_key_index = (self._next_key_index + 1) % key_count

        return index

    def _should_try_next_key(
        self,
        error: Exception,
    ) -> bool:
        status_code = getattr(error, "status_code", None)

        if status_code in {401, 403, 413, 429}:
            return True

        if status_code is not None and status_code >= 500:
            return True

        message = str(error).lower()

        retry_markers = [
            "rate limit",
            "rate_limit",
            "request_too_large",
            "request entity too large",
            "server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        ]

        return any(marker in message for marker in retry_markers)


    def _build_messages(
        self,
        request: AIRequest,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []

        system_parts: list[str] = []

        if request.instructions:
            system_parts.append(request.instructions.strip())

        if request.response_format:
            system_parts.append(f"Response format: {request.response_format}")

        if request.text_files:
            system_parts.append(
                "The user provided text files. Their contents are included in the user message."
            )

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

        user_parts: list[str] = []

        for text_file in request.text_files:
            user_parts.append(
                "\n".join(
                    [
                        f"Text file: {text_file.filename}",
                        "```",
                        text_file.content,
                        "```",
                    ]
                )
            )

        user_parts.append(request.text.strip())

        messages.append(
            {
                "role": "user",
                "content": "\n\n".join(part for part in user_parts if part.strip()),
            }
        )

        return messages

    def _map_role(
        self,
        role: AIMessageRole,
    ) -> str:
        if role == AIMessageRole.ASSISTANT:
            return "assistant"

        if role == AIMessageRole.SYSTEM:
            return "system"

        return "user"

    def _extract_text(
        self,
        completion: Any,
    ) -> str:
        choices = getattr(completion, "choices", None)

        if not choices:
            return ""

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        content = getattr(message, "content", None)

        if content is None:
            return ""

        return str(content)

    def _extract_stream_delta(
        self,
        chunk: Any,
    ) -> str:
        choices = getattr(chunk, "choices", None)

        if not choices:
            return ""

        first_choice = choices[0]
        delta = getattr(first_choice, "delta", None)
        content = getattr(delta, "content", None)

        if content is None:
            return ""

        return str(content)

    def _extract_finish_reason(
        self,
        completion: Any,
    ) -> str | None:
        choices = getattr(completion, "choices", None)

        if not choices:
            return None

        return getattr(choices[0], "finish_reason", None)

    def _extract_usage(
        self,
        completion: Any,
    ) -> dict[str, Any]:
        usage = getattr(completion, "usage", None)

        if usage is None:
            return {}

        result: dict[str, Any] = {}

        for name in [
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_time",
            "completion_time",
            "total_time",
        ]:
            value = getattr(usage, name, None)
            if value is not None:
                result[name] = value

        return result

