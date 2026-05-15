from collections.abc import AsyncIterator
from typing import Any

from app.application.contracts import (
    AIProviderCapabilities,
    AIProviderLimits,
    AIProviderStatus,
    AIRequest,
    AIResponse,
    AIResponseStatus,
    AIStreamChunk,
    AIStreamEventType,
)
from app.infrastructure.providers.groq.provider import GroqProvider


class GroqSearchProvider(GroqProvider):
    _MAX_SEARCH_PROMPT_LENGTH = 5000
    _MAX_SEARCH_INSTRUCTIONS_LENGTH = 1200
    _MAX_SEARCH_COMPLETION_TOKENS = 1200
    _FALLBACK_SEARCH_MODEL = "groq/compound"

    @property
    def name(self) -> str:
        return "groq_search"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(
            can_stream=True,
            can_stream_message_edits=False,
            can_analyze_images=False,
            can_search_web_natively=True,
            can_use_files=False,
            max_media_count=0,
            max_text_length=8000,
        )

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=8000,
            max_media_count=0,
            max_media_caption_length=0,
            max_message_count_per_request=1,
            one_active_request_per_session=False,
            send_large_text_as_file=False,
            request_timeout_seconds=self._config.timeout_seconds,
            retry_count=self._config.max_retries,
            retry_delay_seconds=self._config.retry_delay_seconds,
        )

    @property
    def status(self) -> AIProviderStatus:
        if not self._config.get_all_api_keys():
            return AIProviderStatus(
                available=False,
                reason="GROQ_API_KEYS is not configured",
            )

        return AIProviderStatus(available=True)

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponse:
        keys = self._config.get_all_api_keys()
        models = self._get_search_models()

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
                    "models": models,
                    "key_count": 0,
                },
            )

        start_index = self._select_start_key_index(len(keys))
        errors: list[str] = []

        for model in models:
            for offset in range(len(keys)):
                key_index = (start_index + offset) % len(keys)

                try:
                    return await self._generate_search_with_model_key(
                        request=request,
                        model=model,
                        key_index=key_index,
                    )
                except Exception as exc:
                    error_text = f"{type(exc).__name__}: {exc}"
                    errors.append(f"{model} key[{key_index}]: {error_text}")

                    if not self._should_try_next_key(exc):
                        break

        return AIResponse(
            status=AIResponseStatus.ERROR,
            text="",
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
            error=f"{self.name} provider failed with all available API keys and models",
            metadata={
                "provider": self.name,
                "models": models,
                "key_count": len(keys),
                "key_errors": errors,
            },
        )

    async def _generate_search_with_model_key(
        self,
        request: AIRequest,
        model: str,
        key_index: int,
    ) -> AIResponse:
        client = self._get_client(key_index)
        messages = self._build_messages(request)

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self._config.temperature,
            max_completion_tokens=self._MAX_SEARCH_COMPLETION_TOKENS,
            compound_custom={
                "tools": {
                    "enabled_tools": ["web_search"],
                },
            },
            extra_headers={
                "Groq-Model-Version": "latest",
            },
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
                "models": self._get_search_models(),
                "key_index": key_index,
                "key_count": len(self._config.get_all_api_keys()),
                "usage": self._extract_usage(completion),
                "finish_reason": self._extract_finish_reason(completion),
                "max_completion_tokens": self._MAX_SEARCH_COMPLETION_TOKENS,
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
        keys = self._config.get_all_api_keys()
        models = self._get_search_models()

        if not keys:
            yield AIStreamChunk(
                event_type=AIStreamEventType.ERROR,
                provider_name=self.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error="GROQ_API_KEYS is not configured",
                metadata={
                    "provider": self.name,
                    "models": models,
                    "key_count": 0,
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                    "stream_transport": "groq_search_native_stream",
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
                "models": models,
                "key_count": len(keys),
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_search_native_stream",
            },
        )

        start_index = self._select_start_key_index(len(keys))
        errors: list[str] = []

        for model in models:
            for offset in range(len(keys)):
                key_index = (start_index + offset) % len(keys)

                try:
                    async for chunk in self._stream_search_with_model_key(
                        request=request,
                        model=model,
                        key_index=key_index,
                    ):
                        yield chunk
                    return
                except Exception as exc:
                    error_text = f"{type(exc).__name__}: {exc}"
                    errors.append(f"{model} key[{key_index}]: {error_text}")

                    if not self._should_try_next_key(exc):
                        break

        yield AIStreamChunk(
            event_type=AIStreamEventType.ERROR,
            provider_name=self.name,
            session_id=request.session_id,
            request_id=request.request_id,
            error=f"{self.name} provider stream failed with all available API keys and models",
            metadata={
                "provider": self.name,
                "models": models,
                "key_count": len(keys),
                "key_errors": errors,
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_search_native_stream",
            },
        )

    async def _stream_search_with_model_key(
        self,
        request: AIRequest,
        model: str,
        key_index: int,
    ) -> AsyncIterator[AIStreamChunk]:
        client = self._get_client(key_index)
        messages = self._build_messages(request)
        full_text = ""
        finish_reason: str | None = None

        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self._config.temperature,
            max_completion_tokens=self._MAX_SEARCH_COMPLETION_TOKENS,
            compound_custom={
                "tools": {
                    "enabled_tools": ["web_search"],
                },
            },
            extra_headers={
                "Groq-Model-Version": "latest",
            },
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
                    "models": self._get_search_models(),
                    "key_index": key_index,
                    "key_count": len(self._config.get_all_api_keys()),
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                    "stream_transport": "groq_search_native_stream",
                    "max_completion_tokens": self._MAX_SEARCH_COMPLETION_TOKENS,
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
                "models": self._get_search_models(),
                "key_index": key_index,
                "key_count": len(self._config.get_all_api_keys()),
                "finish_reason": finish_reason,
                "request_id": request.request_id,
                "session_id": request.session_id,
                "stream_transport": "groq_search_native_stream",
                "max_completion_tokens": self._MAX_SEARCH_COMPLETION_TOKENS,
            },
        )

    def _get_model(self) -> str:
        return self._config.search_model

    def _get_search_models(self) -> list[str]:
        result = []

        for model in [
            self._config.search_model,
            self._FALLBACK_SEARCH_MODEL,
        ]:
            if model and model not in result:
                result.append(model)

        return result

    def _build_messages(
        self,
        request: AIRequest,
    ) -> list[dict[str, Any]]:
        system_parts = [
            "You are a compact web-search assistant.",
            "Use web search when the model supports it.",
            "Return concise findings with dates, source names, and URLs when available.",
            "Do not include long background text.",
        ]

        if request.instructions:
            system_parts.append(
                "Extra instructions:\n"
                + self._compact_text(
                    request.instructions,
                    max_length=self._MAX_SEARCH_INSTRUCTIONS_LENGTH,
                )
            )

        user_parts = [
            "Search task:",
            self._compact_text(
                request.text,
                max_length=self._MAX_SEARCH_PROMPT_LENGTH,
            ),
        ]

        return [
            {
                "role": "system",
                "content": "\n\n".join(system_parts),
            },
            {
                "role": "user",
                "content": "\n".join(user_parts),
            },
        ]

    def _extract_text(
        self,
        completion: Any,
    ) -> str:
        text = super()._extract_text(completion)

        if text.strip():
            return text

        return self._extract_text_from_executed_tools(completion)

    def _extract_text_from_executed_tools(
        self,
        completion: Any,
    ) -> str:
        for choice in self._read_items(completion, "choices"):
            message = self._read_value(choice, "message")

            for tool in self._read_items(message, "executed_tools"):
                search_results = self._read_value(tool, "search_results")
                results = self._read_items(search_results, "results")

                if results:
                    return self._format_search_results(results)

                output = self._read_value(tool, "output")

                if isinstance(output, str) and output.strip():
                    return self._compact_text(output, max_length=5000)

        return ""

    def _format_search_results(
        self,
        results: list[Any],
    ) -> str:
        lines = ["Search results returned by Groq Compound:"]

        for index, item in enumerate(results[:5], start=1):
            title = self._read_string_value(item, "title") or "Untitled"
            url = self._read_string_value(item, "url")
            content = self._read_string_value(item, "content")

            lines.append("")
            lines.append(f"{index}. {title}")

            if url:
                lines.append(f"URL: {url}")

            if content:
                lines.append(
                    "Snippet: "
                    + self._compact_text(content, max_length=600)
                )

        return "\n".join(lines).strip()

    def _read_items(
        self,
        value: Any,
        key: str,
    ) -> list[Any]:
        nested = self._read_value(value, key)

        if isinstance(nested, list):
            return nested

        return []

    def _read_string_value(
        self,
        value: Any,
        key: str,
    ) -> str:
        nested = self._read_value(value, key)

        if isinstance(nested, str):
            return nested.strip()

        return ""

    def _read_value(
        self,
        value: Any,
        key: str,
    ) -> Any:
        if value is None:
            return None

        if isinstance(value, dict):
            return value.get(key)

        return getattr(value, key, None)

    def _compact_text(
        self,
        text: str,
        max_length: int,
    ) -> str:
        normalized = " ".join(text.split())

        if len(normalized) <= max_length:
            return normalized

        return normalized[: max_length - 20].rstrip() + " ...[truncated]"
