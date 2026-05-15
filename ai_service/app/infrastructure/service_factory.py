from app.application.agent_core.runner import AgentRunner
from app.application.agent_core.tools import AgentToolRegistry
from app.application.ai_client import AIClient
from app.application.ai_service import AIService
from app.application.ai_sessions import AIConversationStore
from app.application.cache import (
    AIAnalysisCacheKeyBuilder,
    AICacheStore,
    MemoryAICacheStore,
)
from app.application.contracts import AIContentRegistry, AIProviderRoutingConfig
from app.application.db import AIDatabaseGateway, NullAIDatabaseGateway
from app.application.observability import AIEventLogger, NullAIEventLogger
from app.application.parsing import AnalysisResponseParser
from app.application.poster_agent.pipeline import PosterAgentPipeline
from app.application.prompting import ContentPromptBuilder, JsonRepairPromptBuilder
from app.application.serialization import AIAnalysisResultSerializer
from app.application.session_locks import AISessionLockManager
from app.application.sql import AISqlPlanValidator
from app.application.validation import AIAnalysisResultValidator
from app.infrastructure.agent_tools import (
    GroqSearchAgentTool,
    UrlReadAgentTool,
)
from app.infrastructure.conversation_store import build_conversation_store
from app.infrastructure.env import load_env_file
from app.infrastructure.providers import build_provider_router
from app.infrastructure.telegram_debug import (
    TelegramVisualDebugSink,
    TelegramAgentRunDebugSink,
    TelegramAIVisualDebugSink,
    load_telegram_visual_debug_config,
)


_telegram_visual_debug_sink: TelegramVisualDebugSink | None = None
_telegram_visual_debug_sink_enabled: bool | None = None


def _build_shared_telegram_visual_debug_sink() -> TelegramVisualDebugSink | None:
    global _telegram_visual_debug_sink
    global _telegram_visual_debug_sink_enabled

    config = load_telegram_visual_debug_config()

    if not config.enabled:
        _telegram_visual_debug_sink_enabled = False
        return None

    if (
        _telegram_visual_debug_sink is not None
        and _telegram_visual_debug_sink_enabled is True
    ):
        return _telegram_visual_debug_sink

    _telegram_visual_debug_sink = TelegramVisualDebugSink(config=config)
    _telegram_visual_debug_sink_enabled = True

    return _telegram_visual_debug_sink


def _build_telegram_debug_sink(
    telegram_sink: TelegramVisualDebugSink | None = None,
) -> TelegramAIVisualDebugSink | None:
    config = load_telegram_visual_debug_config()

    if not config.enabled:
        return None

    return TelegramAIVisualDebugSink(
        config=config,
        telegram_sink=telegram_sink,
    )


def _build_telegram_agent_run_debug_sink(
    telegram_sink: TelegramVisualDebugSink | None = None,
) -> TelegramAgentRunDebugSink | None:
    config = load_telegram_visual_debug_config()

    if not config.enabled:
        return None

    return TelegramAgentRunDebugSink(
        config=config,
        telegram_sink=telegram_sink,
    )

async def flush_telegram_visual_debug_sink() -> None:
    sink = _build_shared_telegram_visual_debug_sink()

    if sink is None:
        return

    await sink.flush()


def build_ai_service(
    provider_names: list[str] | None = None,
    routing_config: AIProviderRoutingConfig | None = None,
    content_registry: AIContentRegistry | None = None,
    cache_store: AICacheStore | None = None,
    database_gateway: AIDatabaseGateway | None = None,
    event_logger: AIEventLogger | None = None,
) -> AIService:
    load_env_file()

    registry = content_registry or AIContentRegistry()
    telegram_sink = _build_shared_telegram_visual_debug_sink()

    return AIService(
        provider_router=build_provider_router(
            debug_sink=_build_telegram_debug_sink(telegram_sink),
            provider_names=provider_names,
            routing_config=routing_config,
        ),
        content_registry=registry,
        content_prompt_builder=ContentPromptBuilder(
            content_registry=registry,
        ),
        json_repair_prompt_builder=JsonRepairPromptBuilder(),
        analysis_response_parser=AnalysisResponseParser(
            content_registry=registry,
        ),
        sql_plan_validator=AISqlPlanValidator(),
        analysis_result_validator=AIAnalysisResultValidator(),
        analysis_result_serializer=AIAnalysisResultSerializer(),
        analysis_cache_key_builder=AIAnalysisCacheKeyBuilder(),
        cache_store=cache_store or MemoryAICacheStore(),
        database_gateway=database_gateway or NullAIDatabaseGateway(),
        session_lock_manager=AISessionLockManager(),
        event_logger=event_logger or NullAIEventLogger(),
    )


def build_ai_client(
    provider_names: list[str] | None = None,
    routing_config: AIProviderRoutingConfig | None = None,
    content_registry: AIContentRegistry | None = None,
    cache_store: AICacheStore | None = None,
    database_gateway: AIDatabaseGateway | None = None,
    event_logger: AIEventLogger | None = None,
    conversation_store: AIConversationStore | None = None,
) -> AIClient:
    return AIClient(
        service=build_ai_service(
            provider_names=provider_names,
            routing_config=routing_config,
            content_registry=content_registry,
            cache_store=cache_store,
            database_gateway=database_gateway,
            event_logger=event_logger,
        ),
        conversation_store=conversation_store or build_conversation_store(),
    )


def build_agent_tool_registry(
    ai_client: AIClient,
    include_search: bool = True,
    include_url_read: bool = True,
) -> AgentToolRegistry:
    registry = AgentToolRegistry()

    if include_search:
        registry.register(
            GroqSearchAgentTool(
                ai_client=ai_client,
            )
        )

    if include_url_read:
        registry.register(
            UrlReadAgentTool()
        )

    return registry


def build_agent_runner(
    ai_client: AIClient | None = None,
    tool_registry: AgentToolRegistry | None = None,
    provider_names: list[str] | None = None,
    routing_config: AIProviderRoutingConfig | None = None,
    content_registry: AIContentRegistry | None = None,
    cache_store: AICacheStore | None = None,
    database_gateway: AIDatabaseGateway | None = None,
    event_logger: AIEventLogger | None = None,
    conversation_store: AIConversationStore | None = None,
) -> AgentRunner:
    client = ai_client or build_ai_client(
        provider_names=provider_names,
        routing_config=routing_config,
        content_registry=content_registry,
        cache_store=cache_store,
        database_gateway=database_gateway,
        event_logger=event_logger,
        conversation_store=conversation_store,
    )

    return AgentRunner(
        ai_client=client,
        tool_registry=tool_registry or build_agent_tool_registry(client),
    )


def build_poster_agent_pipeline(
    ai_client: AIClient | None = None,
    agent_runner: AgentRunner | None = None,
    tool_registry: AgentToolRegistry | None = None,
    provider_names: list[str] | None = None,
    routing_config: AIProviderRoutingConfig | None = None,
    content_registry: AIContentRegistry | None = None,
    cache_store: AICacheStore | None = None,
    database_gateway: AIDatabaseGateway | None = None,
    event_logger: AIEventLogger | None = None,
    conversation_store: AIConversationStore | None = None,
) -> PosterAgentPipeline:
    if agent_runner is not None:
        return PosterAgentPipeline(
            agent_runner=agent_runner,
        agent_run_debug_sink=_build_telegram_agent_run_debug_sink(
            _build_shared_telegram_visual_debug_sink(),
        ),
        )

    runner = build_agent_runner(
        ai_client=ai_client,
        tool_registry=tool_registry,
        provider_names=provider_names,
        routing_config=routing_config,
        content_registry=content_registry,
        cache_store=cache_store,
        database_gateway=database_gateway,
        event_logger=event_logger,
        conversation_store=conversation_store,
    )

    return PosterAgentPipeline(
        agent_runner=runner,
        agent_run_debug_sink=_build_telegram_agent_run_debug_sink(
            _build_shared_telegram_visual_debug_sink(),
        ),
    )
    



