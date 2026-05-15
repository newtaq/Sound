import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.application.ai_debug import AIVisualDebugSink
from app.application.contracts import (
    AIProvider,
    AIProviderRoutingConfig,
    AIRequest,
    AIResponse,
    AIResponseStatus,
    AIStreamChunk,
    AIStreamEventType,
    StreamingAIProvider,
)
from app.application.provider_request_builder import AIProviderRequestBuilder


class AIProviderRouter:
    def __init__(
        self,
        providers: list[AIProvider],
        request_builder: AIProviderRequestBuilder | None = None,
        routing_config: AIProviderRoutingConfig | None = None,
        debug_sink: AIVisualDebugSink | None = None,
    ) -> None:
        if not providers:
            raise ValueError("At least one AI provider is required")

        self._providers = {provider.name: provider for provider in providers}
        self._provider_order = [provider.name for provider in providers]
        self._default_provider_name = providers[0].name
        self._request_builder = request_builder or AIProviderRequestBuilder()
        self._routing_config = routing_config or AIProviderRoutingConfig()
        self._debug_sink = debug_sink

    def get_provider(self, name: str | None = None) -> AIProvider:
        provider_name = name or self._default_provider_name
        provider = self._providers.get(provider_name)

        if provider is None:
            available = ", ".join(sorted(self._providers))
            raise ValueError(
                f"Unknown AI provider: {provider_name}. Available providers: {available}"
            )

        return provider

    async def generate(self, request: AIRequest) -> AIResponse:
        self._emit_debug_request(request)

        if request.provider_name:
            response = await self._generate_with_explicit_provider(request)
        else:
            response = await self._generate_with_fallback(request)

        response = self._with_request_id(response, request)
        self._emit_debug_response(request, response)

        return response

    def _emit_debug_request(
        self,
        request: AIRequest,
    ) -> None:
        if self._debug_sink is None:
            return

        try:
            self._debug_sink.emit_request(
                request=request,
                provider_name=request.provider_name,
            )
        except Exception:
            return

    def _emit_debug_response(
        self,
        request: AIRequest,
        response: AIResponse,
    ) -> None:
        if self._debug_sink is None:
            return

        try:
            self._debug_sink.emit_response(
                request=request,
                response=response,
            )
        except Exception:
            return

    def _emit_debug_stream_chunk(
        self,
        request: AIRequest,
        chunk: AIStreamChunk,
    ) -> None:
        if self._debug_sink is None:
            return

        try:
            self._debug_sink.emit_stream_chunk(
                request=request,
                chunk=chunk,
            )
        except Exception:
            return

    def _with_request_id(
        self,
        response: AIResponse,
        request: AIRequest,
    ) -> AIResponse:
        if response.request_id is None:
            response.request_id = request.request_id

        response.metadata = self._with_request_metadata(
            metadata=response.metadata,
            request=request,
        )

        return response

    def _with_request_metadata(
        self,
        metadata: dict[str, Any],
        request: AIRequest,
    ) -> dict[str, Any]:
        return {
            **metadata,
            "request_id": request.request_id,
            "session_id": request.session_id,
        }

    async def _generate_with_explicit_provider(
        self,
        request: AIRequest,
    ) -> AIResponse:
        provider = self.get_provider(request.provider_name)
        status = provider.status

        if not status.available:
            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=provider.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error=(
                    f"Provider {provider.name} is unavailable"
                    + (f": {status.reason}" if status.reason else "")
                ),
                metadata=self._with_request_metadata(
                    metadata={
                        "requested_provider": provider.name,
                        "fallback_allowed": False,
                    },
                    request=request,
                ),
            )

        response = await self._generate_with_provider(provider, request)
        response.metadata = {
            **response.metadata,
            "requested_provider": provider.name,
            "fallback_allowed": False,
        }

        return response

    async def _generate_with_fallback(
        self,
        request: AIRequest,
    ) -> AIResponse:
        errors: list[str] = []

        for provider_name in self._provider_order:
            provider = self.get_provider(provider_name)
            status = provider.status

            if not status.available:
                errors.append(
                    f"{provider.name}: unavailable"
                    + (f" ({status.reason})" if status.reason else "")
                )

                if not self._routing_config.enable_fallback:
                    break

                continue

            response = await self._generate_with_provider(provider, request)

            if response.status == AIResponseStatus.OK:
                if errors:
                    response.metadata = {
                        **response.metadata,
                        "fallback_errors": errors,
                    }
                return response

            errors.append(
                f"{provider.name}: {response.error or response.status.value}"
            )

            if not self._routing_config.enable_fallback:
                break

        return AIResponse(
            status=AIResponseStatus.ERROR,
            text="",
            provider_name=self._provider_order[0] if self._provider_order else None,
            session_id=request.session_id,
            request_id=request.request_id,
            error=(
                "AI provider failed"
                if not self._routing_config.enable_fallback
                else "All AI providers failed"
            ),
            metadata=self._with_request_metadata(
                metadata={
                    "fallback_errors": errors,
                    "fallback_allowed": self._routing_config.enable_fallback,
                },
                request=request,
            ),
        )

    def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        self._emit_debug_request(request)

        return self._stream_with_debug(request)

    async def _stream_with_debug(
        self,
        request: AIRequest,
    ) -> AsyncIterator[AIStreamChunk]:
        async for chunk in self._stream(request):
            self._emit_debug_stream_chunk(request, chunk)
            yield chunk

    async def _stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        provider = self.get_provider(request.provider_name)
        status = provider.status
        explicit_provider = request.provider_name is not None

        if not status.available:
            if (
                self._routing_config.stream_fallback_to_generate
                and not explicit_provider
            ):
                async for chunk in self._generate_as_stream(request):
                    yield chunk
                return

            yield AIStreamChunk(
                event_type=AIStreamEventType.ERROR,
                provider_name=provider.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error=(
                    f"Provider {provider.name} is unavailable"
                    + (f": {status.reason}" if status.reason else "")
                ),
                metadata=self._with_request_metadata(
                    metadata={
                        "requested_provider": request.provider_name,
                        "fallback_allowed": (
                            False
                            if explicit_provider
                            else self._routing_config.stream_fallback_to_generate
                        ),
                    },
                    request=request,
                ),
            )
            return

        limit_error = self._validate_non_text_limits(provider, request)

        if limit_error is not None:
            limit_error = self._with_request_id(limit_error, request)

            if (
                self._routing_config.stream_fallback_to_generate
                and not explicit_provider
            ):
                async for chunk in self._response_as_stream(limit_error):
                    yield chunk
                return

            async for chunk in self._response_as_stream(limit_error):
                yield chunk
            return

        if not isinstance(provider, StreamingAIProvider):
            if (
                self._routing_config.stream_fallback_to_generate
                and not explicit_provider
            ):
                async for chunk in self._generate_as_stream(request):
                    yield chunk
                return

            yield AIStreamChunk(
                event_type=AIStreamEventType.ERROR,
                provider_name=provider.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error=f"Provider {provider.name} does not support streaming",
                metadata=self._with_request_metadata(
                    metadata={
                        "requested_provider": request.provider_name,
                        "fallback_allowed": (
                            False
                            if explicit_provider
                            else self._routing_config.stream_fallback_to_generate
                        ),
                    },
                    request=request,
                ),
            )
            return

        request_parts = self._build_request_parts(provider, request)

        if len(request_parts) != 1:
            if self._routing_config.stream_fallback_to_generate:
                response = await self._generate_with_provider(provider, request)
                response = self._with_request_id(response, request)

                async for chunk in self._response_as_stream(response):
                    yield chunk
                return

            yield AIStreamChunk(
                event_type=AIStreamEventType.ERROR,
                provider_name=provider.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error="Streaming multipart requests are not supported yet",
                metadata=self._with_request_metadata(
                    metadata={
                        "requested_provider": request.provider_name,
                        "fallback_allowed": False,
                    },
                    request=request,
                ),
            )
            return

        request_parts[0].request_id = request.request_id

        try:
            async for chunk in provider.stream(request_parts[0]):
                if chunk.request_id is None:
                    chunk.request_id = request.request_id

                chunk.metadata = self._with_request_metadata(
                    metadata=chunk.metadata,
                    request=request,
                )

                yield chunk
        except Exception as error:
            if (
                not self._routing_config.stream_fallback_to_generate
                or explicit_provider
            ):
                yield AIStreamChunk(
                    event_type=AIStreamEventType.ERROR,
                    provider_name=provider.name,
                    session_id=request.session_id,
                    request_id=request.request_id,
                    error=f"{type(error).__name__}: {error}",
                    metadata=self._with_request_metadata(
                        metadata={
                            "requested_provider": request.provider_name,
                            "fallback_allowed": (
                                False
                                if explicit_provider
                                else self._routing_config.stream_fallback_to_generate
                            ),
                        },
                        request=request,
                    ),
                )
                return

            async for chunk in self._generate_as_stream(request):
                yield chunk

    async def _generate_as_stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        response = await self.generate(request)
        async for chunk in self._response_as_stream(response):
            yield chunk

    async def _response_as_stream(
        self,
        response: AIResponse,
    ) -> AsyncIterator[AIStreamChunk]:
        metadata = {
            **response.metadata,
            "request_id": response.request_id,
            "session_id": response.session_id,
            "stream_fallback_to_generate": True,
        }

        if response.status == AIResponseStatus.OK:
            yield AIStreamChunk(
                event_type=AIStreamEventType.FINISHED,
                text=response.text,
                full_text=response.text,
                provider_name=response.provider_name,
                session_id=response.session_id,
                request_id=response.request_id,
                attachments=response.attachments,
                metadata=metadata,
            )
            return

        yield AIStreamChunk(
            event_type=AIStreamEventType.ERROR,
            provider_name=response.provider_name,
            session_id=response.session_id,
            request_id=response.request_id,
            attachments=response.attachments,
            metadata=metadata,
            error=response.error or response.status.value,
        )

    async def _generate_with_provider(
        self,
        provider: AIProvider,
        request: AIRequest,
    ) -> AIResponse:
        limit_error = self._validate_non_text_limits(provider, request)
        if limit_error is not None:
            return self._with_request_id(limit_error, request)

        request_parts = self._build_request_parts(provider, request)

        message_count_error = self._validate_message_count(provider, request_parts)
        if message_count_error is not None:
            return self._with_request_id(message_count_error, request)

        responses: list[AIResponse] = []

        for request_part in request_parts:
            request_part.provider_name = provider.name
            request_part.request_id = request.request_id

            response = await self._safe_generate_with_retries(provider, request_part)
            response = self._with_request_id(response, request)
            responses.append(response)

            if response.status != AIResponseStatus.OK:
                return response

        if len(responses) == 1:
            return responses[0]

        return AIResponse(
            status=responses[-1].status,
            text=responses[-1].text,
            provider_name=provider.name,
            session_id=request.session_id,
            request_id=request.request_id,
            raw_messages=[response.text for response in responses],
            attachments=responses[-1].attachments,
            metadata=self._with_request_metadata(
                metadata={
                    **request.metadata,
                    "is_multipart": True,
                    "part_total": len(responses),
                },
                request=request,
            ),
            error=responses[-1].error,
        )

    async def _safe_generate_with_retries(
        self,
        provider: AIProvider,
        request: AIRequest,
    ) -> AIResponse:
        attempts = max(1, provider.limits.retry_count + 1)
        last_response: AIResponse | None = None

        for attempt_index in range(attempts):
            if attempt_index > 0 and provider.limits.retry_delay_seconds > 0:
                await asyncio.sleep(provider.limits.retry_delay_seconds)

            response = await self._safe_generate_once(provider, request)
            response = self._with_request_id(response, request)

            if response.status == AIResponseStatus.OK:
                if attempt_index > 0:
                    response.metadata = {
                        **response.metadata,
                        "retry_attempts": attempt_index,
                    }
                return response

            last_response = response

        if last_response is None:
            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=provider.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error="Provider did not return a response",
                metadata=self._with_request_metadata(
                    metadata={},
                    request=request,
                ),
            )

        if provider.limits.retry_count > 0:
            last_response.metadata = {
                **last_response.metadata,
                "retry_attempts": attempts - 1,
            }

        return last_response

    async def _safe_generate_once(
        self,
        provider: AIProvider,
        request: AIRequest,
    ) -> AIResponse:
        try:
            timeout = provider.limits.request_timeout_seconds

            if timeout is None:
                return await provider.generate(request)

            return await asyncio.wait_for(
                provider.generate(request),
                timeout=timeout,
            )
        except TimeoutError:
            return AIResponse(
                status=AIResponseStatus.TIMEOUT,
                text="",
                provider_name=provider.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error=(
                    "Provider request timeout after "
                    f"{provider.limits.request_timeout_seconds} seconds"
                ),
                metadata=self._with_request_metadata(
                    metadata={},
                    request=request,
                ),
            )
        except Exception as error:
            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=provider.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error=f"{type(error).__name__}: {error}",
                metadata=self._with_request_metadata(
                    metadata={},
                    request=request,
                ),
            )

    def _build_request_parts(
        self,
        provider: AIProvider,
        request: AIRequest,
    ) -> list[AIRequest]:
        request_parts = self._request_builder.build_parts(
            request=request,
            max_text_length=provider.limits.max_text_length,
            send_large_text_as_file=provider.limits.send_large_text_as_file,
            max_media_count=provider.limits.max_media_count,
        )

        for request_part in request_parts:
            request_part.request_id = request.request_id

        return request_parts

    def _validate_message_count(
        self,
        provider: AIProvider,
        request_parts: list[AIRequest],
    ) -> AIResponse | None:
        limit = provider.limits.max_message_count_per_request

        if limit is None:
            return None

        if len(request_parts) <= limit:
            return None

        first_part = request_parts[0] if request_parts else None

        return AIResponse(
            status=AIResponseStatus.ERROR,
            text="",
            provider_name=provider.name,
            session_id=first_part.session_id if first_part else None,
            request_id=first_part.request_id if first_part else None,
            error=(
                f"Too many message parts for provider {provider.name}: "
                f"{len(request_parts)} > {limit}"
            ),
        )

    def _validate_non_text_limits(
        self,
        provider: AIProvider,
        request: AIRequest,
    ) -> AIResponse | None:
        limits = provider.limits

        if request.media and limits.max_media_count <= 0:
            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=provider.name,
                session_id=request.session_id,
                request_id=request.request_id,
                error=f"Provider {provider.name} does not support media",
            )

        return None
    

