import json
from collections.abc import AsyncIterator

from app.application.contracts import (
    AIProviderCapabilities,
    AIProviderLimits,
    AIRequest,
    AIResponse,
    AIResponseStatus,
    AIStreamChunk,
    AIStreamEventType,
    StreamingAIProvider,
)


class MockAIProvider(StreamingAIProvider):
    @property
    def name(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(
            can_stream=True,
            can_stream_message_edits=True,
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
            max_media_caption_length=None,
            max_message_count_per_request=None,
            one_active_request_per_session=True,
            send_large_text_as_file=False,
        )

    async def generate(self, request: AIRequest) -> AIResponse:
        text = json.dumps(
            {
                "status": "ok",
                "provider": self.name,
                "session_id": request.session_id,
                "text": request.text,
                "text_files": [
                    {
                        "filename": text_file.filename,
                        "mime_type": text_file.mime_type,
                        "content_length": len(text_file.content),
                    }
                    for text_file in request.text_files
                ],
            },
            ensure_ascii=False,
        )

        return AIResponse(
            status=AIResponseStatus.OK,
            text=text,
            provider_name=self.name,
            session_id=request.session_id,
            raw_messages=[text],
        )

    def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        return self._stream(request)

    async def _stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        yield AIStreamChunk(
            event_type=AIStreamEventType.STARTED,
            provider_name=self.name,
            session_id=request.session_id,
        )

        full_text = ""
        for part in ["mock ", "stream ", "response"]:
            full_text += part
            yield AIStreamChunk(
                event_type=AIStreamEventType.MESSAGE_UPDATED,
                text=part,
                full_text=full_text,
                provider_name=self.name,
                session_id=request.session_id,
            )

        yield AIStreamChunk(
            event_type=AIStreamEventType.FINISHED,
            full_text=full_text,
            provider_name=self.name,
            session_id=request.session_id,
        )
        

