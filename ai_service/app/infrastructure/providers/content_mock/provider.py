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


class ContentMockAIProvider(StreamingAIProvider):
    @property
    def name(self) -> str:
        return "content_mock"

    @property
    def capabilities(self) -> AIProviderCapabilities:
        return AIProviderCapabilities(
            can_stream=True,
            can_stream_message_edits=True,
            can_analyze_images=True,
            can_search_web_natively=True,
            can_use_files=True,
            max_media_count=10,
            max_text_length=None,
        )

    @property
    def limits(self) -> AIProviderLimits:
        return AIProviderLimits(
            max_text_length=None,
            max_media_count=10,
            max_media_caption_length=None,
            max_message_count_per_request=None,
            one_active_request_per_session=True,
            send_large_text_as_file=False,
            request_timeout_seconds=None,
            retry_count=0,
            retry_delay_seconds=0.0,
        )

    async def generate(self, request: AIRequest) -> AIResponse:
        decision_data = {
            "tour_title": "Кишлак. Тур 2026",
            "artists": ["Кишлак"],
            "occurrences": [
                {
                    "city": "Москва",
                    "date": "2026-05-12",
                    "venue": None,
                },
                {
                    "city": "Санкт-Петербург",
                    "date": "2026-05-14",
                    "venue": None,
                },
            ],
        }

        evidence = [
            {
                "field": "artist",
                "value": "Кишлак",
                "source": "text",
                "source_text": "Кишлак. Тур 2026.",
                "confidence": 0.9,
                "metadata": {},
            },
            {
                "field": "date_city",
                "value": {
                    "city": "Москва",
                    "date": "2026-05-12",
                },
                "source": "text",
                "source_text": "12 мая — Москва",
                "confidence": 0.9,
                "metadata": {},
            },
            {
                "field": "date_city",
                "value": {
                    "city": "Санкт-Петербург",
                    "date": "2026-05-14",
                },
                "source": "text",
                "source_text": "14 мая — Санкт-Петербург",
                "confidence": 0.9,
                "metadata": {},
            },
        ]

        text = json.dumps(
            {
                "content_type": "tour_announcement",
                "is_useful": True,
                "priority": "high",
                "confidence": 0.9,
                "main_decision": "create_tour_candidate",
                "decisions": [
                    {
                        "type": "create_tour_candidate",
                        "confidence": 0.9,
                        "data": decision_data,
                        "evidence": evidence,
                    }
                ],
                "variants": [
                    {
                        "decision": "create_tour_candidate",
                        "confidence": 0.9,
                        "data": decision_data,
                    }
                ],
                "sql_plan": [],
                "warnings": [],
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
        response = await self.generate(request)

        yield AIStreamChunk(
            event_type=AIStreamEventType.STARTED,
            provider_name=self.name,
            session_id=request.session_id,
        )

        yield AIStreamChunk(
            event_type=AIStreamEventType.MESSAGE_UPDATED,
            text=response.text,
            full_text=response.text,
            provider_name=self.name,
            session_id=request.session_id,
        )

        yield AIStreamChunk(
            event_type=AIStreamEventType.FINISHED,
            full_text=response.text,
            provider_name=self.name,
            session_id=request.session_id,
        )
        

