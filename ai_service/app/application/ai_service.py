from collections.abc import AsyncIterator
from dataclasses import replace
from time import perf_counter
from typing import Any

from app.application.cache import (
    AIAnalysisCacheKeyBuilder,
    AICacheStore,
    MemoryAICacheStore,
)
from app.application.contracts import (
    AIAnalysisResult,
    AIContentInput,
    AIContentRegistry,
    AIParsedAnalysis,
    AIRequest,
    AIResponse,
    AIStreamChunk,
)
from app.application.db import AIDatabaseGateway, NullAIDatabaseGateway
from app.application.observability import (
    AIEvent,
    AIEventLevel,
    AIEventLogger,
    NullAIEventLogger,
)
from app.application.parsing import AnalysisResponseParser
from app.application.prompting import ContentPromptBuilder, JsonRepairPromptBuilder
from app.application.provider_router import AIProviderRouter
from app.application.serialization import AIAnalysisResultSerializer
from app.application.session_locks import AISessionLockManager
from app.application.sql import AISqlPlanValidator
from app.application.validation import AIAnalysisResultValidator


class AIService:
    def __init__(
        self,
        provider_router: AIProviderRouter,
        content_registry: AIContentRegistry | None = None,
        content_prompt_builder: ContentPromptBuilder | None = None,
        json_repair_prompt_builder: JsonRepairPromptBuilder | None = None,
        analysis_response_parser: AnalysisResponseParser | None = None,
        sql_plan_validator: AISqlPlanValidator | None = None,
        analysis_result_validator: AIAnalysisResultValidator | None = None,
        analysis_result_serializer: AIAnalysisResultSerializer | None = None,
        analysis_cache_key_builder: AIAnalysisCacheKeyBuilder | None = None,
        cache_store: AICacheStore | None = None,
        database_gateway: AIDatabaseGateway | None = None,
        session_lock_manager: AISessionLockManager | None = None,
        event_logger: AIEventLogger | None = None,
    ) -> None:
        self._provider_router = provider_router
        self._content_registry = content_registry or AIContentRegistry()
        self._content_prompt_builder = content_prompt_builder or ContentPromptBuilder(
            content_registry=self._content_registry,
        )
        self._json_repair_prompt_builder = json_repair_prompt_builder or JsonRepairPromptBuilder()
        self._analysis_response_parser = analysis_response_parser or AnalysisResponseParser(
            content_registry=self._content_registry,
        )
        self._sql_plan_validator = sql_plan_validator or AISqlPlanValidator()
        self._analysis_result_validator = analysis_result_validator or AIAnalysisResultValidator()
        self._analysis_result_serializer = analysis_result_serializer or AIAnalysisResultSerializer()
        self._analysis_cache_key_builder = analysis_cache_key_builder or AIAnalysisCacheKeyBuilder()
        self._cache_store = cache_store or MemoryAICacheStore()
        self._database_gateway = database_gateway or NullAIDatabaseGateway()
        self._session_lock_manager = session_lock_manager or AISessionLockManager()
        self._event_logger = event_logger or NullAIEventLogger()

    async def generate(self, request: AIRequest) -> AIResponse:
        started_at = perf_counter()

        await self._log_event(
            name="provider_generate_started",
            level=AIEventLevel.DEBUG,
            message="AI provider generate request started",
            session_id=request.session_id,
            provider_name=request.provider_name,
            metadata={
                "task": request.metadata.get("task"),
                "text_length": len(request.text),
                "media_count": len(request.media),
            },
        )

        try:
            async with self._session_lock_manager.lock(request.session_id):
                response = await self._provider_router.generate(request)
        except Exception as error:
            await self._log_event(
                name="provider_generate_error",
                level=AIEventLevel.ERROR,
                message="AI provider generate request failed",
                session_id=request.session_id,
                provider_name=request.provider_name,
                metadata={
                    "task": request.metadata.get("task"),
                    "error": f"{type(error).__name__}: {error}",
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            raise

        await self._log_event(
            name="provider_generate_finished",
            level=AIEventLevel.INFO,
            message="AI provider generate request finished",
            session_id=request.session_id,
            provider_name=response.provider_name or request.provider_name,
            metadata={
                "task": request.metadata.get("task"),
                "status": response.status,
                "error": response.error,
                "text_length": len(response.text),
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )

        return response

    def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        return self._stream_locked(request)

    async def _stream_locked(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        started_at = perf_counter()
        chunks_count = 0

        await self._log_event(
            name="provider_stream_started",
            level=AIEventLevel.DEBUG,
            message="AI provider stream request started",
            session_id=request.session_id,
            provider_name=request.provider_name,
            metadata={
                "task": request.metadata.get("task"),
                "text_length": len(request.text),
                "media_count": len(request.media),
            },
        )

        try:
            async with self._session_lock_manager.lock(request.session_id):
                async for chunk in self._provider_router.stream(request):
                    chunks_count += 1
                    yield chunk
        except Exception as error:
            await self._log_event(
                name="provider_stream_error",
                level=AIEventLevel.ERROR,
                message="AI provider stream request failed",
                session_id=request.session_id,
                provider_name=request.provider_name,
                metadata={
                    "task": request.metadata.get("task"),
                    "error": f"{type(error).__name__}: {error}",
                    "chunks_count": chunks_count,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            raise

        await self._log_event(
            name="provider_stream_finished",
            level=AIEventLevel.INFO,
            message="AI provider stream request finished",
            session_id=request.session_id,
            provider_name=request.provider_name,
            metadata={
                "task": request.metadata.get("task"),
                "chunks_count": chunks_count,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )

    async def analyze_content(
        self,
        content: AIContentInput,
        provider_name: str | None = None,
        session_id: str | None = None,
    ) -> AIResponse:
        content = await self._with_database_context(
            content=content,
            session_id=session_id,
            provider_name=provider_name,
        )

        prompt = self._content_prompt_builder.build(content)
        source_item_id = content.source_item_id or content.source_post_id

        request = AIRequest(
            text=prompt,
            session_id=session_id,
            provider_name=provider_name,
            media=content.media,
            metadata={
                "task": "analyze_incoming_content",
                "source_type": content.source_type,
                "source_platform": content.source_platform,
                "source_id": content.source_id,
                "source_item_id": source_item_id,
                "source_url": content.source_url,
            },
        )

        return await self.generate(request)

    async def repair_analysis_response(
        self,
        broken_text: str,
        parse_error: str | None = None,
        provider_name: str | None = None,
        session_id: str | None = None,
    ) -> AIResponse:
        prompt = self._json_repair_prompt_builder.build(
            broken_text=broken_text,
            parse_error=parse_error,
        )

        request = AIRequest(
            text=prompt,
            session_id=session_id,
            provider_name=provider_name,
            metadata={
                "task": "repair_json_response",
            },
        )

        return await self.generate(request)

    async def analyze_content_parsed(
        self,
        content: AIContentInput,
        provider_name: str | None = None,
        session_id: str | None = None,
    ) -> AIParsedAnalysis:
        response = await self.analyze_content(
            content=content,
            provider_name=provider_name,
            session_id=session_id,
        )

        parsed = self._analysis_response_parser.parse(response)
        if parsed.ok:
            return parsed

        repaired_response = await self.repair_analysis_response(
            broken_text=response.text,
            parse_error=parsed.error,
            provider_name=provider_name,
            session_id=session_id,
        )

        repaired = self._analysis_response_parser.parse(repaired_response)
        if repaired.ok:
            repaired.warnings.append("Response was repaired by AI provider")

        return repaired

    async def analyze_content_result(
        self,
        content: AIContentInput,
        provider_name: str | None = None,
        session_id: str | None = None,
    ) -> AIAnalysisResult | None:
        cache_key = self._analysis_cache_key_builder.build_content_key(
            content=content,
            provider_name=provider_name,
        )

        cached_result = await self._load_analysis_result_from_cache(cache_key)
        if cached_result is not None:
            await self._log_event(
                name="analysis_cache_hit",
                level=AIEventLevel.INFO,
                message="Loaded analysis result from cache",
                session_id=session_id,
                provider_name=provider_name,
                metadata={
                    "cache_key": cache_key,
                    "source_type": content.source_type,
                    "source_platform": content.source_platform,
                    "source_item_id": content.source_item_id or content.source_post_id,
                },
            )

            cached_result.warnings.append("Loaded analysis result from cache")
            return cached_result

        await self._log_event(
            name="analysis_cache_miss",
            level=AIEventLevel.DEBUG,
            message="Analysis result was not found in cache",
            session_id=session_id,
            provider_name=provider_name,
            metadata={
                "cache_key": cache_key,
                "source_type": content.source_type,
                "source_platform": content.source_platform,
                "source_item_id": content.source_item_id or content.source_post_id,
            },
        )

        result = await self._analyze_content_result_uncached(
            content=content,
            provider_name=provider_name,
            session_id=session_id,
        )

        if result is None:
            return None

        await self._save_analysis_result(result)
        await self._save_analysis_result_to_cache(cache_key, result)

        return result

    async def _analyze_content_result_uncached(
        self,
        content: AIContentInput,
        provider_name: str | None,
        session_id: str | None,
    ) -> AIAnalysisResult | None:
        response = await self.analyze_content(
            content=content,
            provider_name=provider_name,
            session_id=session_id,
        )

        result = self._analysis_response_parser.parse_result(response)

        if result is None:
            parsed = self._analysis_response_parser.parse(response)

            repaired_response = await self.repair_analysis_response(
                broken_text=response.text,
                parse_error=parsed.error,
                provider_name=provider_name,
                session_id=session_id,
            )

            result = self._analysis_response_parser.parse_result(repaired_response)
            if result is not None:
                result.warnings.append("Response was repaired by AI provider")

        if result is None:
            return None

        sql_validation = self._sql_plan_validator.validate_plan(result.sql_plan)
        if not sql_validation.ok:
            result.warnings.extend(sql_validation.errors)

        result_validation = self._analysis_result_validator.validate(result)
        if result_validation.errors:
            result.warnings.extend(result_validation.errors)
        if result_validation.warnings:
            result.warnings.extend(result_validation.warnings)

        return result

    async def _load_analysis_result_from_cache(
        self,
        cache_key: str,
    ) -> AIAnalysisResult | None:
        cached_value = await self._cache_store.get(cache_key)

        if not isinstance(cached_value, dict):
            return None

        return self._analysis_result_serializer.from_dict(cached_value)

    async def _save_analysis_result_to_cache(
        self,
        cache_key: str,
        result: AIAnalysisResult,
    ) -> None:
        try:
            await self._cache_store.set(
                cache_key,
                self._analysis_result_serializer.to_dict(result),
            )
        except Exception as error:
            result.warnings.append(
                f"Failed to cache analysis result: {type(error).__name__}: {error}"
            )

    async def _with_database_context(
        self,
        content: AIContentInput,
        session_id: str | None = None,
        provider_name: str | None = None,
    ) -> AIContentInput:
        source_item_id = content.source_item_id or content.source_post_id

        try:
            db_context = await self._database_gateway.search_context(
                query=content.text,
                limit=20,
            )
        except Exception as error:
            error_text = f"{type(error).__name__}: {error}"

            await self._log_event(
                name="db_context_error",
                level=AIEventLevel.WARNING,
                message="Failed to load database context",
                session_id=session_id,
                provider_name=provider_name,
                metadata={
                    "error": error_text,
                    "source_type": content.source_type,
                    "source_platform": content.source_platform,
                    "source_item_id": source_item_id,
                },
            )

            return replace(
                content,
                metadata={
                    **content.metadata,
                    "db_context": [],
                    "db_context_error": error_text,
                },
            )

        normalized_context = self._normalize_db_context(db_context)

        await self._log_event(
            name="db_context_loaded",
            level=AIEventLevel.DEBUG,
            message="Loaded database context for content analysis",
            session_id=session_id,
            provider_name=provider_name,
            metadata={
                "items_count": len(normalized_context),
                "source_type": content.source_type,
                "source_platform": content.source_platform,
                "source_item_id": source_item_id,
            },
        )

        return replace(
            content,
            metadata={
                **content.metadata,
                "db_context": normalized_context,
            },
        )

    def _normalize_db_context(
        self,
        db_context: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for item in db_context:
            normalized_item: dict[str, Any] = {}

            for key, value in item.items():
                if isinstance(key, str):
                    normalized_item[key] = value

            result.append(normalized_item)

        return result

    async def _log_event(
        self,
        name: str,
        level: AIEventLevel = AIEventLevel.INFO,
        message: str | None = None,
        session_id: str | None = None,
        provider_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            await self._event_logger.log(
                AIEvent(
                    name=name,
                    level=level,
                    message=message,
                    session_id=session_id,
                    provider_name=provider_name,
                    metadata=metadata or {},
                )
            )
        except Exception:
            return None

    async def _save_analysis_result(self, result: AIAnalysisResult) -> None:
        try:
            await self._database_gateway.save_analysis_result(
                self._analysis_result_serializer.to_dict(result)
            )
        except Exception as error:
            result.warnings.append(
                f"Failed to save analysis result: {type(error).__name__}: {error}"
            )
            

