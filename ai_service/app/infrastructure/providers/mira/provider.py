import asyncio
from collections.abc import AsyncIterator

from app.application.contracts import (
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
from app.infrastructure.providers.mira.client import (
    MiraTelegramClient,
    MiraTelegramSentMessage,
)
from app.infrastructure.providers.mira.config import (
    MiraTelegramProviderConfig,
    load_mira_telegram_config,
)
from app.infrastructure.providers.mira.request_payload import (
    MiraTelegramOutgoingMessage,
    MiraTelegramRequestPacker,
)
from app.infrastructure.providers.mira.response_tracker import (
    MiraTelegramResponseTracker,
)
from app.infrastructure.providers.mira.topics import MiraTelegramTopicManager


class MiraTelegramProvider(StreamingAIProvider):
    def __init__(
        self,
        config: MiraTelegramProviderConfig | None = None,
        client: MiraTelegramClient | None = None,
        response_tracker: MiraTelegramResponseTracker | None = None,
        topic_manager: MiraTelegramTopicManager | None = None,
    ) -> None:
        self._config = config or load_mira_telegram_config()
        self._request_packer = MiraTelegramRequestPacker(self._config)
        self._client = client or MiraTelegramClient(self._config)
        self._response_tracker = response_tracker or MiraTelegramResponseTracker(
            self._config
        )
        self._topic_manager = topic_manager or MiraTelegramTopicManager(self._config)
        self._request_lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "mira_telegram"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(
            can_stream=True,
            can_stream_message_edits=False,
            can_analyze_images=True,
            can_search_web_natively=True,
            can_use_files=True,
            max_media_count=self._config.max_media_count,
            max_text_length=self._config.max_text_message_length,
        )

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=self._config.max_text_message_length,
            max_media_count=self._config.max_media_count,
            max_media_caption_length=self._config.max_caption_length,
            max_message_count_per_request=None,
            one_active_request_per_session=(
                self._config.one_active_request_per_session
            ),
            send_large_text_as_file=self._config.send_large_text_as_file,
            request_timeout_seconds=self._config.request_timeout_seconds,
            retry_count=self._config.max_retries,
            retry_delay_seconds=self._config.retry_delay_seconds,
        )

    @property
    def status(self) -> AIProviderStatus:
        if self._config.api_id is None:
            return AIProviderStatus(
                available=False,
                reason="AI_PROVIDER_MIRA_TELEGRAM_API_ID is not configured",
            )

        if not self._config.api_hash:
            return AIProviderStatus(
                available=False,
                reason="AI_PROVIDER_MIRA_TELEGRAM_API_HASH is not configured",
            )

        if not self._config.bot_username and self._config.chat_id is None:
            return AIProviderStatus(
                available=False,
                reason="Mira Telegram bot username or chat id is not configured",
            )

        if (
            self._config.forum_topics_enabled
            and self._config.chat_id is not None
            and not self._config.bot_token
        ):
            return AIProviderStatus(
                available=False,
                reason=(
                    "AI_PROVIDER_MIRA_TELEGRAM_BOT_TOKEN is required "
                    "when forum topics are enabled"
                ),
            )

        return AIProviderStatus(available=True)

    async def generate(self, request: AIRequest) -> AIResponse:
        if self._config.one_active_request_per_session:
            async with self._request_lock:
                return await self._generate_locked(request)

        return await self._generate_locked(request)

    async def _generate_locked(self, request: AIRequest) -> AIResponse:
        chat_id = self._client.chat_id
        message_thread_id = await self._get_message_thread_id(request)
        outgoing_messages = self._request_packer.build_messages(request)

        sent_messages: list[MiraTelegramSentMessage] = []

        try:
            await self._client.start()

            waiter = await self._response_tracker.prepare_response_waiter(
                client=self._client.raw_client,
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )

            try:
                sent_messages = await self._client.send_messages(
                    messages=outgoing_messages,
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                )

                response = await waiter.wait(
                    after_message_id=self._get_last_sent_message_id(sent_messages),
                )
            except Exception:
                waiter.close()
                raise

        except Exception as exc:
            topic_status_metadata = await self._update_topic_status(request, "error")

            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=self.name,
                session_id=request.session_id,
                error=str(exc),
                metadata={
                    **topic_status_metadata,
                    "stage": "telegram_request",
                    "chat_id": chat_id,
                    "message_thread_id": message_thread_id,
                    "outgoing_message_count": len(outgoing_messages),
                    "sent_message_count": len(sent_messages),
                    "outgoing_messages": self._serialize_outgoing_messages(
                        outgoing_messages
                    ),
                    "sent_messages": self._serialize_sent_messages(sent_messages),
                },
            )

        if not response.text.strip() and not response.attachments:
            topic_status_metadata = await self._update_topic_status(request, "error")

            return AIResponse(
                status=AIResponseStatus.ERROR,
                text="",
                provider_name=self.name,
                session_id=request.session_id,
                error="Mira did not return a text or attachment response",
                metadata={
                    **topic_status_metadata,
                    "stage": "telegram_response",
                    "finish_reason": response.finish_reason,
                    "chat_id": chat_id,
                    "message_thread_id": message_thread_id,
                    "outgoing_message_count": len(outgoing_messages),
                    "sent_message_count": len(sent_messages),
                    "outgoing_messages": self._serialize_outgoing_messages(
                        outgoing_messages
                    ),
                    "sent_messages": self._serialize_sent_messages(sent_messages),
                    "response_message_ids": response.message_ids,
                },
            )

        topic_status_metadata = await self._update_topic_status(request, "finished")

        return AIResponse(
            status=AIResponseStatus.OK,
            text=response.text,
            provider_name=self.name,
            session_id=request.session_id,
            attachments=response.attachments,
            metadata={
                **topic_status_metadata,
                "stage": "telegram_response",
                "telegram_sent": True,
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "finish_reason": response.finish_reason,
                "outgoing_message_count": len(outgoing_messages),
                "sent_message_count": len(sent_messages),
                "outgoing_messages": self._serialize_outgoing_messages(
                    outgoing_messages
                ),
                "sent_messages": self._serialize_sent_messages(sent_messages),
                "response_message_ids": response.message_ids,
                "response_attachment_count": len(response.attachments),
            },
        )

    def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        return self._stream(request)

    async def _stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        if self._config.one_active_request_per_session:
            async with self._request_lock:
                async for chunk in self._stream_locked(request):
                    yield chunk
            return

        async for chunk in self._stream_locked(request):
            yield chunk

    async def _stream_locked(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        chat_id = self._client.stream_chat_id
        message_thread_id = await self._get_stream_message_thread_id(
            request=request,
            chat_id=chat_id,
        )
        outgoing_messages = self._request_packer.build_messages(request)

        yield AIStreamChunk(
            event_type=AIStreamEventType.STARTED,
            provider_name=self.name,
            session_id=request.session_id,
            metadata={
                "stage": "telegram_stream_started",
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "stream_transport": "telegram_final_message_fallback",
                "native_draft_stream_observable": False,
                "outgoing_message_count": len(outgoing_messages),
                "outgoing_messages": self._serialize_outgoing_messages(
                    outgoing_messages
                ),
            },
        )

        sent_messages: list[MiraTelegramSentMessage] = []

        try:
            await self._client.start()

            waiter = await self._response_tracker.prepare_response_waiter(
                client=self._client.raw_client,
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )

            try:
                sent_messages = await self._client.send_messages(
                    messages=outgoing_messages,
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                )

                response = await waiter.wait(
                    after_message_id=self._get_last_sent_message_id(sent_messages),
                )
            except Exception:
                waiter.close()
                raise

            if not response.text.strip() and not response.attachments:
                topic_status_metadata = await self._update_topic_status(request, "error")

                yield AIStreamChunk(
                    event_type=AIStreamEventType.ERROR,
                    provider_name=self.name,
                    session_id=request.session_id,
                    error="Mira did not return a text or attachment response",
                    metadata={
                        **topic_status_metadata,
                        "stage": "telegram_stream_response",
                        "chat_id": chat_id,
                        "message_thread_id": message_thread_id,
                        "finish_reason": response.finish_reason,
                        "stream_transport": "telegram_final_message_fallback",
                        "native_draft_stream_observable": False,
                        "sent_message_count": len(sent_messages),
                        "sent_messages": self._serialize_sent_messages(sent_messages),
                        "response_message_ids": response.message_ids,
                    },
                )
                return

            yield AIStreamChunk(
                event_type=AIStreamEventType.MESSAGE_UPDATED,
                text=response.text,
                full_text=response.text,
                provider_name=self.name,
                session_id=request.session_id,
                attachments=response.attachments,
                metadata={
                    "stage": "telegram_stream_final_message",
                    "chat_id": chat_id,
                    "message_thread_id": message_thread_id,
                    "finish_reason": response.finish_reason,
                    "stream_transport": "telegram_final_message_fallback",
                    "native_draft_stream_observable": False,
                    "response_message_ids": response.message_ids,
                    "response_attachment_count": len(response.attachments),
                },
            )

            topic_status_metadata = await self._update_topic_status(request, "finished")

            yield AIStreamChunk(
                event_type=AIStreamEventType.FINISHED,
                full_text=response.text,
                provider_name=self.name,
                session_id=request.session_id,
                attachments=response.attachments,
                metadata={
                    **topic_status_metadata,
                    "stage": "telegram_stream_finished",
                    "chat_id": chat_id,
                    "message_thread_id": message_thread_id,
                    "finish_reason": response.finish_reason,
                    "stream_transport": "telegram_final_message_fallback",
                    "native_draft_stream_observable": False,
                    "outgoing_message_count": len(outgoing_messages),
                    "sent_message_count": len(sent_messages),
                    "outgoing_messages": self._serialize_outgoing_messages(
                        outgoing_messages
                    ),
                    "sent_messages": self._serialize_sent_messages(sent_messages),
                    "response_message_ids": response.message_ids,
                    "response_attachment_count": len(response.attachments),
                },
            )

        except Exception as exc:
            topic_status_metadata = await self._update_topic_status(request, "error")

            yield AIStreamChunk(
                event_type=AIStreamEventType.ERROR,
                provider_name=self.name,
                session_id=request.session_id,
                error=str(exc),
                metadata={
                    **topic_status_metadata,
                    "stage": "telegram_stream_error",
                    "chat_id": chat_id,
                    "message_thread_id": message_thread_id,
                    "stream_transport": "telegram_final_message_fallback",
                    "native_draft_stream_observable": False,
                    "outgoing_message_count": len(outgoing_messages),
                    "sent_message_count": len(sent_messages),
                    "outgoing_messages": self._serialize_outgoing_messages(
                        outgoing_messages
                    ),
                    "sent_messages": self._serialize_sent_messages(sent_messages),
                },
            )

    async def _update_topic_status(
        self,
        request: AIRequest,
        status: str,
    ) -> dict:
        result = {
            "topic_status_update_requested": True,
            "topic_status": status,
            "topic_status_updated": False,
            "topic_status_thread_id": None,
            "topic_status_error": None,
        }

        try:
            thread_id = await self._topic_manager.update_request_status(
                session_id=request.session_id,
                status=status,
                mode=request.mode,
                request_id=request.request_id,
            )
        except Exception as exc:
            result["topic_status_error"] = f"{type(exc).__name__}: {exc}"
            return result

        result["topic_status_thread_id"] = thread_id
        result["topic_status_updated"] = thread_id is not None

        return result

    async def _get_stream_message_thread_id(
        self,
        request: AIRequest,
        chat_id: int | str | None,
    ) -> int | None:
        if chat_id != self._client.chat_id:
            return None

        return await self._get_message_thread_id(request)

    async def _get_message_thread_id(
        self,
        request: AIRequest,
    ) -> int | None:
        if request.session_id is None:
            return None

        return await self._topic_manager.register_request(
            session_id=request.session_id,
            mode=request.mode,
            status="active",
            request_id=request.request_id,
        )

    def _get_last_sent_message_id(
        self,
        sent_messages: list[MiraTelegramSentMessage],
    ) -> int | None:
        message_ids = [
            message.message_id
            for message in sent_messages
            if message.message_id is not None
        ]

        if not message_ids:
            return None

        return max(message_ids)

    def _serialize_outgoing_messages(
        self,
        messages: list[MiraTelegramOutgoingMessage],
    ) -> list[dict]:
        return [
            {
                "kind": message.kind.value,
                "text_length": len(message.text or ""),
                "attachment_kinds": [
                    attachment.kind.value
                    for attachment in message.attachments
                ],
                "attachment_count": len(message.attachments),
                "metadata": message.metadata,
            }
            for message in messages
        ]

    def _serialize_sent_messages(
        self,
        messages: list[MiraTelegramSentMessage],
    ) -> list[dict]:
        return [
            {
                "message_id": message.message_id,
                "chat_id": message.chat_id,
                "message_thread_id": message.message_thread_id,
                "text_length": len(message.text or ""),
                "caption_length": len(message.caption or ""),
            }
            for message in messages
        ]
        

