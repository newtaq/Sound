import json

from app.application.agent_core import (
    AgentEvidenceSet,
    AgentPlan,
    AgentRun,
    AgentRunDebugSink,
    AgentRunner,
    AgentRunRequest,
    AgentToolOutput,
)
from app.application.poster_agent.draft_builder import (
    PosterAgentDraftBuildRequest,
    PosterAgentDraftBuilder,
)
from app.application.poster_agent.draft_validator import PosterAgentDraftValidator
from app.application.poster_agent.event_summary_renderer import (
    PosterEventSummaryRenderer,
)
from app.application.poster_agent.pipeline_draft_sync import (
    PosterAgentPipelineDraftSync,
)
from app.application.poster_agent.pipeline_evidence_fallback import (
    PosterAgentPipelineEvidenceFallback,
)
from app.application.poster_agent.pipeline_goal_builder import (
    PosterAgentPipelineGoalBuilder,
)
from app.application.poster_agent.pipeline_models import (
    PosterAgentPipelineRequest,
    PosterAgentPipelineResult,
)
from app.application.poster_agent.post_text_renderer import PosterPostTextRenderer
from app.application.poster_agent.publish_decision_engine import (
    PosterPublishDecisionEngine,
)
from app.application.poster_agent.renderer import PosterAgentRenderer
from app.application.poster_agent.verification_models import (
    PosterAgentVerificationResult,
)
from app.application.poster_agent.verification_parser import (
    PosterAgentVerificationParseError,
    PosterAgentVerificationParser,
)
from app.application.poster_agent.verification_prompt_builder import (
    PosterAgentVerificationPromptBuilder,
)
from app.application.poster_agent.verification_result_sanitizer import (
    PosterAgentVerificationResultSanitizer,
)


class PosterAgentPipeline:
    def __init__(
        self,
        agent_runner: AgentRunner,
        draft_builder: PosterAgentDraftBuilder | None = None,
        draft_validator: PosterAgentDraftValidator | None = None,
        publish_decision_engine: PosterPublishDecisionEngine | None = None,
        renderer: PosterAgentRenderer | None = None,
        verification_parser: PosterAgentVerificationParser | None = None,
        verification_prompt_builder: PosterAgentVerificationPromptBuilder | None = None,
        agent_run_debug_sink: AgentRunDebugSink | None = None,
        post_text_renderer: PosterPostTextRenderer | None = None,
        event_summary_renderer: PosterEventSummaryRenderer | None = None,
        goal_builder: PosterAgentPipelineGoalBuilder | None = None,
        verification_sanitizer: PosterAgentVerificationResultSanitizer | None = None,
        draft_sync: PosterAgentPipelineDraftSync | None = None,
        evidence_fallback: PosterAgentPipelineEvidenceFallback | None = None,
    ) -> None:
        self._agent_runner = agent_runner
        self._draft_builder = draft_builder or PosterAgentDraftBuilder()
        self._draft_validator = draft_validator or PosterAgentDraftValidator()
        self._publish_decision_engine = (
            publish_decision_engine or PosterPublishDecisionEngine()
        )
        self._renderer = renderer or PosterAgentRenderer()
        self._post_text_renderer = post_text_renderer or PosterPostTextRenderer()
        self._event_summary_renderer = (
            event_summary_renderer or PosterEventSummaryRenderer()
        )
        self._verification_parser = (
            verification_parser or PosterAgentVerificationParser()
        )
        self._verification_prompt_builder = (
            verification_prompt_builder or PosterAgentVerificationPromptBuilder()
        )
        self._agent_run_debug_sink = agent_run_debug_sink

        self._goal_builder = goal_builder or PosterAgentPipelineGoalBuilder()
        self._verification_sanitizer = (
            verification_sanitizer
            or PosterAgentVerificationResultSanitizer(self._goal_builder)
        )
        self._draft_sync = draft_sync or PosterAgentPipelineDraftSync()
        self._evidence_fallback = (
            evidence_fallback
            or PosterAgentPipelineEvidenceFallback(self._verification_parser)
        )

    def _build_visual_debug_metadata(
        self,
        request: PosterAgentPipelineRequest,
    ):
        return self._goal_builder.build_visual_debug_metadata(request)

    def _build_urls_for_verification(
        self,
        request: PosterAgentPipelineRequest,
    ):
        return self._goal_builder.build_urls_for_verification(request)

    def _build_goal(
        self,
        request: PosterAgentPipelineRequest,
        urls_for_verification: list[str],
    ):
        return self._goal_builder.build_goal(
            request=request,
            urls_for_verification=urls_for_verification,
        )

    def _build_required_tools(
        self,
        request: PosterAgentPipelineRequest,
        urls_for_verification: list[str],
    ):
        return self._goal_builder.build_required_tools(
            request=request,
            urls_for_verification=urls_for_verification,
        )

    def _build_default_search_query(
        self,
        input_text: str,
    ) -> str:
        return self._goal_builder.build_default_search_query(input_text)

    def _extract_urls_from_text(
        self,
        text: str,
    ) -> list[str]:
        return self._goal_builder.extract_urls_from_text(text)

    def _extract_event_title_from_text(
        self,
        text: str,
    ) -> str | None:
        return self._goal_builder.extract_event_title_from_text(text)

    def _extract_event_date_from_text(
        self,
        text: str,
    ) -> str | None:
        return self._goal_builder.extract_event_date_from_text(text)

    async def run(
        self,
        request: PosterAgentPipelineRequest,
    ) -> PosterAgentPipelineResult:
        urls_for_verification = self._goal_builder.build_urls_for_verification(request)
        debug_metadata = self._goal_builder.build_visual_debug_metadata(request)

        agent_run = await self._run_agent(
            request=request,
            urls_for_verification=urls_for_verification,
            debug_metadata=debug_metadata,
        )

        verification_result, verification_error = self._build_verification_result(
            agent_run=agent_run,
            request=request,
            urls_for_verification=urls_for_verification,
        )

        draft = self._build_draft(agent_run)

        verification_metrics = self._apply_verification_to_draft(
            agent_run=agent_run,
            draft=draft,
            verification_result=verification_result,
        )

        decision = self._build_publish_decision(
            draft=draft,
            verification_result=verification_result,
            verification_metrics=verification_metrics,
        )

        review_text = self._renderer.render_review_text(
            draft=draft,
            decision=decision,
        )
        post_text = self._build_post_text(
            verification_result=verification_result,
            agent_run=agent_run,
        )
        event_summary_text = self._build_event_summary_text(
            verification_result=verification_result,
            decision=decision,
        )

        self._store_rendered_outputs(
            agent_run=agent_run,
            draft=draft,
            decision=decision,
            review_text=review_text,
            post_text=post_text,
            event_summary_text=event_summary_text,
        )

        self._emit_agent_run_debug(agent_run)

        return PosterAgentPipelineResult(
            agent_run=agent_run,
            draft=draft,
            decision=decision,
            review_text=review_text,
            post_text=post_text,
            event_summary_text=event_summary_text,
            verification_result=verification_result,
            verification_error=verification_error,
        )

    async def _run_agent(
        self,
        request: PosterAgentPipelineRequest,
        urls_for_verification: list[str],
        debug_metadata: dict,
    ) -> AgentRun:
        return await self._agent_runner.run(
            AgentRunRequest(
                goal=self._goal_builder.build_goal(
                    request=request,
                    urls_for_verification=urls_for_verification,
                ),
                session_id=request.session_id,
                provider_name=request.provider_name,
                mode=request.mode,
                max_steps=request.max_steps,
                required_tools=self._goal_builder.build_required_tools(
                    request=request,
                    urls_for_verification=urls_for_verification,
                ),
                extract_evidence=True,
                adaptive_tools=request.adaptive_tools,
                final_prompt_builder=(
                    self._build_verification_final_prompt
                    if request.structured_verification
                    else None
                ),
                final_instructions=(
                    self._build_verification_final_instructions()
                    if request.structured_verification
                    else None
                ),
                final_response_format="plain_text",
                media=request.media,
                metadata={
                    **debug_metadata,
                    **request.metadata,
                    "poster_agent_pipeline": True,
                    "use_search": request.use_search,
                    "use_url_read": request.use_url_read,
                    "adaptive_tools": request.adaptive_tools,
                    "structured_verification": request.structured_verification,
                    "explicit_verify_url_count": len(request.verify_urls),
                    "total_verify_url_count": len(urls_for_verification),
                    "media_count": len(request.media),
                },
            )
        )

    def _build_verification_result(
        self,
        agent_run: AgentRun,
        request: PosterAgentPipelineRequest,
        urls_for_verification: list[str],
    ) -> tuple[PosterAgentVerificationResult | None, str | None]:
        verification_result, verification_error = self._parse_verification_result(
            agent_run=agent_run,
            enabled=request.structured_verification,
        )

        if verification_result is None and request.structured_verification:
            fallback_result = self._evidence_fallback.build(
                agent_run=agent_run,
                request=request,
                reason=verification_error,
            )

            if fallback_result is not None:
                verification_result = fallback_result
                verification_error = None

        self._attach_verification_to_agent_run(
            agent_run=agent_run,
            verification_result=verification_result,
            verification_error=verification_error,
        )

        if verification_result is not None:
            self._sanitize_and_store_verification_result(
                agent_run=agent_run,
                verification_result=verification_result,
                request=request,
                urls_for_verification=urls_for_verification,
            )

        return verification_result, verification_error

    def _build_draft(
        self,
        agent_run: AgentRun,
    ):
        return self._draft_builder.build(
            PosterAgentDraftBuildRequest(
                agent_run=agent_run,
            )
        )

    def _apply_verification_to_draft(
        self,
        agent_run: AgentRun,
        draft,
        verification_result: PosterAgentVerificationResult | None,
    ) -> dict[str, object]:
        if verification_result is None:
            return {}

        verification_metrics = self._draft_sync.apply_verification_result(
            draft=draft,
            verification_result=verification_result,
        )
        agent_run.metadata = {
            **agent_run.metadata,
            **verification_metrics,
        }

        return verification_metrics

    def _build_publish_decision(
        self,
        draft,
        verification_result: PosterAgentVerificationResult | None,
        verification_metrics: dict[str, object],
    ):
        validation_decision = self._draft_validator.validate(draft)

        decision = self._publish_decision_engine.decide(
            draft=draft,
            validation_decision=validation_decision,
        )

        return self._draft_sync.normalize_decision(
            decision=decision,
            verification_result=verification_result,
            metrics=verification_metrics,
        )

    def _store_rendered_outputs(
        self,
        agent_run: AgentRun,
        draft,
        decision,
        review_text: str,
        post_text: str,
        event_summary_text: str,
    ) -> None:
        agent_run.metadata = {
            **agent_run.metadata,
            "poster_agent_review_text": review_text,
            "poster_agent_post_text": post_text,
            "poster_agent_event_summary_text": event_summary_text,
            "poster_agent_draft_status": draft.status.value,
            "poster_agent_decision_status": decision.status.value,
            "poster_agent_can_publish": decision.can_publish,
        }

    def _sanitize_and_store_verification_result(
        self,
        agent_run: AgentRun,
        verification_result: PosterAgentVerificationResult,
        request: PosterAgentPipelineRequest,
        urls_for_verification: list[str],
    ) -> None:
        self._verification_sanitizer.sanitize(
            verification_result=verification_result,
            request=request,
            urls_for_verification=urls_for_verification,
        )

        self._verification_sanitizer.apply_url_read_confirmation(
            agent_run=agent_run,
            verification_result=verification_result,
            request=request,
        )

        self._verification_sanitizer.sanitize(
            verification_result=verification_result,
            request=request,
            urls_for_verification=urls_for_verification,
        )

        self._write_verification_result_to_agent_run(
            agent_run=agent_run,
            verification_result=verification_result,
        )

        self._drop_unsafe_agent_evidence(agent_run)

    def _emit_agent_run_debug(
        self,
        agent_run: AgentRun,
    ) -> None:
        if self._agent_run_debug_sink is None:
            return

        self._agent_run_debug_sink.emit_agent_run(agent_run)

    def _build_post_text(
        self,
        verification_result: PosterAgentVerificationResult | None,
        agent_run: AgentRun,
    ) -> str:
        if verification_result is not None:
            return self._post_text_renderer.render(
                verification_result.to_dict(),
            )

        if agent_run.final_result is None:
            return ""

        structured_data = agent_run.final_result.structured_data

        for key in ("poster_verification_result", "poster_verification"):
            value = structured_data.get(key)

            if isinstance(value, dict):
                return self._post_text_renderer.render(value)

        return ""

    def _build_event_summary_text(
        self,
        verification_result: PosterAgentVerificationResult | None,
        decision,
    ) -> str:
        if verification_result is None:
            return ""

        return self._event_summary_renderer.render(
            verification_result.to_dict(),
            status=decision.status.value,
        )

    def _build_verification_final_prompt(
        self,
        goal: str,
        _plan: AgentPlan,
        tool_outputs: list[AgentToolOutput],
        evidence_set: AgentEvidenceSet,
    ) -> str:
        return self._verification_prompt_builder.build_prompt(
            goal=goal,
            tool_outputs=tool_outputs,
            evidence_set=evidence_set,
        )

    def _build_verification_final_instructions(self) -> str:
        return (
            "Ты verifier-агент сервиса афиш. "
            "Верни только строгий JSON результата проверки афиши. "
            "Не добавляй markdown, текст до JSON или текст после JSON. "
            "Не выдумывай даты, годы, площадки, адреса, цены, ссылки и факты. "
            "Данные из поиска считай candidate/unverified, пока они не подтверждены "
            "успешным чтением URL, БД или ручным подтверждением. "
            "Данные из изображения, OCR и входного текста имеют status=input, "
            "но это не равно verified. "
            "Не ставь source_type=manual, если во входных данных явно не сказано, "
            "что пользователь подтвердил факт вручную. "
            "Не добавляй год к дате, если года нет во входном тексте или в явном "
            "ручном подтверждении пользователя. "
            "Если обязательных данных не хватает, укажи missing_fields и "
            "recommendation=needs_review или blocked."
        )

    def _parse_verification_result(
        self,
        agent_run: AgentRun,
        enabled: bool,
    ) -> tuple[PosterAgentVerificationResult | None, str | None]:
        if not enabled:
            return None, None

        if agent_run.final_result is None:
            return None, "Agent final_result is missing"

        try:
            return self._verification_parser.parse(agent_run.final_result.text), None
        except PosterAgentVerificationParseError as exc:
            return None, f"{type(exc).__name__}: {exc}"

    def _attach_verification_to_agent_run(
        self,
        agent_run: AgentRun,
        verification_result: PosterAgentVerificationResult | None,
        verification_error: str | None,
    ) -> None:
        if agent_run.final_result is None:
            return

        if verification_result is not None:
            agent_run.final_result.structured_data["poster_verification"] = (
                verification_result.to_dict()
            )

        if verification_error is not None:
            agent_run.final_result.structured_data["poster_verification_error"] = (
                verification_error
            )

    def _write_verification_result_to_agent_run(
        self,
        agent_run: AgentRun,
        verification_result: PosterAgentVerificationResult,
    ) -> None:
        if agent_run.final_result is None:
            return

        data = verification_result.to_dict()

        agent_run.final_result.text = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        agent_run.final_result.structured_data["poster_verification_result"] = data
        agent_run.final_result.structured_data["poster_verification"] = data
        agent_run.final_result.metadata["poster_verification_sanitized"] = True

    def _drop_unsafe_agent_evidence(
        self,
        agent_run: AgentRun,
    ) -> None:
        raw_evidence_count = len(agent_run.evidence.items)

        agent_run.evidence = AgentEvidenceSet()
        agent_run.metadata = {
            **agent_run.metadata,
            "poster_agent_raw_evidence_dropped": True,
            "poster_agent_raw_evidence_count_before_drop": raw_evidence_count,
            "poster_agent_raw_evidence_drop_reason": (
                "Poster pipeline uses sanitized poster_verification_result "
                "instead of raw LLM evidence."
            ),
        }
        