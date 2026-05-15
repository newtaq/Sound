import json
from dataclasses import dataclass, field
from typing import Any, Callable

from app.application.agent_core.action_parser import (
    AgentActionParseError,
    AgentActionParser,
)
from app.application.agent_core.action_prompt_builder import AgentActionPromptBuilder
from app.application.agent_core.actions import AgentAction
from app.application.agent_core.evidence import AgentEvidenceSet
from app.application.agent_core.evidence_extractor import (
    EvidenceExtractionRequest,
    EvidenceExtractor,
)
from app.application.agent_core.loop_state import (
    AgentLoopState,
    AgentLoopToolCall,
)
from app.application.agent_core.models import (
    AgentFinalResult,
    AgentPlan,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepType,
    AgentToolCall,
    AgentToolResult,
)
from app.application.agent_core.tools import (
    AgentToolInput,
    AgentToolOutput,
    AgentToolRegistry,
)
from app.application.ai_client import AIClient
from app.application.contracts import AIMedia, AIMode, AIResponseStatus


FinalPromptBuilder = Callable[
    [str, AgentPlan, list[AgentToolOutput], AgentEvidenceSet],
    str,
]


@dataclass(slots=True)
class AgentRunRequest:
    goal: str
    session_id: str | None = None
    provider_name: str | None = "groq"
    mode: AIMode = AIMode.DEEP
    max_steps: int = 8
    required_tools: list[AgentToolInput] = field(default_factory=list)
    extract_evidence: bool = True
    adaptive_tools: bool = False
    final_prompt: str | None = None
    final_prompt_builder: FinalPromptBuilder | None = None
    final_instructions: str | None = None
    final_response_format: str = "plain_text"
    media: list[AIMedia] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRunner:
    def __init__(
        self,
        ai_client: AIClient,
        tool_registry: AgentToolRegistry | None = None,
        evidence_extractor: EvidenceExtractor | None = None,
        action_parser: AgentActionParser | None = None,
        action_prompt_builder: AgentActionPromptBuilder | None = None,
    ) -> None:
        self._ai_client = ai_client
        self._tool_registry = tool_registry or AgentToolRegistry()
        self._evidence_extractor = evidence_extractor or EvidenceExtractor(ai_client)
        self._action_parser = action_parser or AgentActionParser()
        self._action_prompt_builder = (
            action_prompt_builder or AgentActionPromptBuilder()
        )

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRun:
        run = AgentRun(
            session_id=request.session_id,
            request_id=None,
            status=AgentRunStatus.RUNNING,
            goal=request.goal,
            metadata={
                **request.metadata,
                "agent_version": "v6",
                "provider_name": request.provider_name,
                "mode": request.mode.value,
                "max_steps": request.max_steps,
                "required_tool_count": len(request.required_tools),
                "extract_evidence": request.extract_evidence,
                "adaptive_tools": request.adaptive_tools,
                "custom_final_prompt": request.final_prompt is not None,
                "custom_final_prompt_builder": request.final_prompt_builder is not None,
                "final_response_format": request.final_response_format,
            },
        )

        plan = self._build_initial_plan(request)
        run.plan = plan

        run.add_step(
            AgentStep(
                index=run.next_step_index(),
                step_type=AgentStepType.THINK,
                content="Создан стартовый план агентного выполнения.",
                metadata={
                    "plan_steps": plan.steps,
                },
            )
        )

        tool_outputs = await self._run_required_tools(
            run=run,
            request=request,
        )

        if request.adaptive_tools:
            adaptive_tool_outputs = await self._run_adaptive_tools(
                run=run,
                request=request,
                previous_tool_outputs=tool_outputs,
            )
            tool_outputs.extend(adaptive_tool_outputs)

        evidence_set = await self._extract_evidence(
            run=run,
            request=request,
            tool_outputs=tool_outputs,
        )
        run.evidence = evidence_set

        final_prompt = self._build_custom_or_default_final_prompt(
            request=request,
            plan=plan,
            tool_outputs=tool_outputs,
            evidence_set=evidence_set,
        )

        final_instructions = request.final_instructions or self._build_agent_instructions()

        try:
            response = await self._ai_client.ask(
                text=final_prompt,
                session_id=request.session_id,
                provider_name=request.provider_name,
                mode=request.mode,
                instructions=final_instructions,
                response_format=request.final_response_format,
                media=request.media,
                use_history=False,
                save_history=True,
                metadata={
                    **request.metadata,
                    "agent_mode": True,
                    "agent_version": "v6",
                    "required_tool_count": len(request.required_tools),
                    "adaptive_tools": request.adaptive_tools,
                    "tool_result_count": len(tool_outputs),
                    "custom_final_prompt": request.final_prompt is not None,
                    "custom_final_prompt_builder": request.final_prompt_builder is not None,
                    "final_response_format": request.final_response_format,
                    "evidence_count": len(evidence_set.items),
                    "verified_evidence_count": len(evidence_set.verified_items()),
                    "unverified_evidence_count": len(evidence_set.unverified_items()),
                    "conflicted_evidence_count": len(evidence_set.conflicted_items()),
                },
            )
        except Exception as exc:
            return self._finish_with_final_fallback(
                run=run,
                request=request,
                tool_outputs=tool_outputs,
                evidence_set=evidence_set,
                provider_name=request.provider_name,
                request_id=run.request_id,
                session_id=run.session_id or request.session_id,
                response_status=None,
                error=f"{type(exc).__name__}: {exc}",
                response_metadata=None,
            )

        run.request_id = response.request_id
        run.session_id = response.session_id

        if response.status != AIResponseStatus.OK:
            return self._finish_with_final_fallback(
                run=run,
                request=request,
                tool_outputs=tool_outputs,
                evidence_set=evidence_set,
                provider_name=response.provider_name,
                request_id=response.request_id,
                session_id=response.session_id,
                response_status=response.status.value,
                error=response.error or response.status.value,
                response_metadata=response.metadata,
            )

        run.add_step(
            AgentStep(
                index=run.next_step_index(),
                step_type=AgentStepType.FINAL,
                content=response.text,
                metadata={
                    "provider_name": response.provider_name,
                    "response_metadata": response.metadata,
                    "tool_result_count": len(tool_outputs),
                  "media_count": len(request.media),
                    "evidence_count": len(evidence_set.items),
                    "verified_evidence_count": len(evidence_set.verified_items()),
                    "unverified_evidence_count": len(evidence_set.unverified_items()),
                    "conflicted_evidence_count": len(evidence_set.conflicted_items()),
                    "custom_final_prompt": request.final_prompt is not None,
                    "custom_final_prompt_builder": request.final_prompt_builder is not None,
                    "final_response_format": request.final_response_format,
                },
            )
        )

        run.final_result = AgentFinalResult(
            text=response.text,
            structured_data={
                "evidence": evidence_set.to_dict(),
                "tool_results": [
                    self._tool_output_to_data(tool_output)
                    for tool_output in tool_outputs
                ],
                "adaptive_tools": request.adaptive_tools,
                "custom_final_prompt": request.final_prompt is not None,
                "custom_final_prompt_builder": request.final_prompt_builder is not None,
                "final_response_format": request.final_response_format,
            },
            metadata={
                "provider_name": response.provider_name,
                "request_id": response.request_id,
                "session_id": response.session_id,
                "response_metadata": response.metadata,
            },
        )
        run.status = AgentRunStatus.FINISHED

        return run

    def _finish_with_final_fallback(
        self,
        *,
        run: AgentRun,
        request: AgentRunRequest,
        tool_outputs: list[AgentToolOutput],
        evidence_set: AgentEvidenceSet,
        provider_name: str | None,
        request_id: str | None,
        session_id: str | None,
        response_status: str | None,
        error: str,
        response_metadata: dict[str, Any] | None = None,
    ) -> AgentRun:
        if request_id is not None:
            run.request_id = request_id

        if session_id is not None:
            run.session_id = session_id

        fallback_text = (
            "Финальный ответ LLM не получен. "
            "Сохранены результаты инструментов и evidence для дальнейшей обработки."
        )

        run.metadata["final_llm_failed"] = True
        run.metadata["final_llm_error"] = error
        run.metadata["final_llm_response_status"] = response_status

        run.add_step(
            AgentStep(
                index=run.next_step_index(),
                step_type=AgentStepType.FINAL,
                content=fallback_text,
                metadata={
                    "provider_name": provider_name,
                    "response_status": response_status,
                    "response_error": error,
                    "response_metadata": response_metadata or {},
                    "tool_result_count": len(tool_outputs),
                    "media_count": len(request.media),
                    "evidence_count": len(evidence_set.items),
                    "verified_evidence_count": len(evidence_set.verified_items()),
                    "unverified_evidence_count": len(evidence_set.unverified_items()),
                    "conflicted_evidence_count": len(evidence_set.conflicted_items()),
                    "custom_final_prompt": request.final_prompt is not None,
                    "custom_final_prompt_builder": request.final_prompt_builder is not None,
                    "final_response_format": request.final_response_format,
                    "final_llm_failed": True,
                    "fallback_final_result": True,
                },
            )
        )

        run.final_result = AgentFinalResult(
            text=fallback_text,
            structured_data={
                "evidence": evidence_set.to_dict(),
                "tool_results": [
                    self._tool_output_to_data(tool_output)
                    for tool_output in tool_outputs
                ],
                "adaptive_tools": request.adaptive_tools,
                "custom_final_prompt": request.final_prompt is not None,
                "custom_final_prompt_builder": request.final_prompt_builder is not None,
                "final_response_format": request.final_response_format,
                "final_llm_failed": True,
                "final_llm_error": error,
                "final_llm_response_status": response_status,
            },
            metadata={
                "provider_name": provider_name,
                "request_id": request_id,
                "session_id": session_id,
                "response_metadata": response_metadata or {},
                "final_llm_failed": True,
                "fallback_final_result": True,
            },
        )

        run.status = AgentRunStatus.FINISHED
        return run

    async def _run_required_tools(
        self,
        run: AgentRun,
        request: AgentRunRequest,
    ) -> list[AgentToolOutput]:
        tool_outputs: list[AgentToolOutput] = []

        for tool_input in request.required_tools:
            if len(tool_outputs) >= request.max_steps:
                break

            tool_output = await self._run_tool_input(
                run=run,
                tool_input=tool_input,
                reason="Обязательный инструмент стартового плана.",
            )
            tool_outputs.append(tool_output)

        return tool_outputs

    async def _run_adaptive_tools(
        self,
        run: AgentRun,
        request: AgentRunRequest,
        previous_tool_outputs: list[AgentToolOutput],
    ) -> list[AgentToolOutput]:
        adaptive_outputs: list[AgentToolOutput] = []

        available_tools = self._tool_registry.list_specs()
        max_adaptive_steps = max(
            request.max_steps - len(previous_tool_outputs),
            0,
        )

        if max_adaptive_steps <= 0:
            run.add_step(
                AgentStep(
                    index=run.next_step_index(),
                    step_type=AgentStepType.THINK,
                    content="Адаптивный цикл не запущен: лимит шагов уже исчерпан.",
                    metadata={
                        "max_steps": request.max_steps,
                        "previous_tool_count": len(previous_tool_outputs),
                    },
                )
            )
            return adaptive_outputs

        state = AgentLoopState(
            goal=request.goal,
            available_tools=available_tools,
            max_steps=max_adaptive_steps,
        )

        self._add_previous_tool_outputs_to_state(
            state=state,
            tool_outputs=previous_tool_outputs,
        )

        while state.can_continue:
            response = await self._ai_client.ask(
                text=self._action_prompt_builder.build_next_action_prompt(state),
                session_id=request.session_id,
                provider_name=request.provider_name,
                mode=request.mode,
                instructions=self._build_action_selection_instructions(),
                response_format="plain_text",
                use_history=False,
                save_history=False,
                metadata={
                    **request.metadata,
                    "agent_mode": True,
                    "agent_version": "v6",
                    "adaptive_action_selection": True,
                    "adaptive_step": state.step_count + 1,
                    "max_adaptive_steps": max_adaptive_steps,
                },
            )

            if response.request_id is not None:
                run.request_id = response.request_id

            if response.session_id is not None:
                run.session_id = response.session_id

            if response.status != AIResponseStatus.OK:
                error = response.error or response.status.value
                run.add_step(
                    AgentStep(
                        index=run.next_step_index(),
                        step_type=AgentStepType.THINK,
                        content=(
                            "Адаптивный цикл остановлен: не удалось получить "
                            "следующее действие агента."
                        ),
                        metadata={
                            "response_status": response.status.value,
                            "response_error": response.error,
                            "adaptive_stopped": True,
                            "non_critical": True,
                        },
                    )
                )
                break

            try:
                action = self._action_parser.parse(response.text)
            except AgentActionParseError as exc:
                error = f"{type(exc).__name__}: {exc}"
                run.add_step(
                    AgentStep(
                        index=run.next_step_index(),
                        step_type=AgentStepType.THINK,
                        content=(
                            "Адаптивный цикл остановлен: модель вернула "
                            "некорректное JSON-действие."
                        ),
                        metadata={
                            "error": error,
                            "raw_response": response.text,
                            "adaptive_stopped": True,
                            "non_critical": True,
                        },
                    )
                )
                break

            state.add_action(action)

            run.add_step(
                AgentStep(
                    index=run.next_step_index(),
                    step_type=AgentStepType.THINK,
                    content=f"Агент выбрал действие: {action.action_type.value}.",
                    metadata={
                        "action": action.to_dict(),
                    },
                )
            )

            if action.is_finish():
                run.add_step(
                    AgentStep(
                        index=run.next_step_index(),
                        step_type=AgentStepType.THINK,
                        content="Адаптивный цикл завершён по решению агента.",
                        metadata={
                            "reason": action.reason,
                            "adaptive_step_count": state.step_count,
                        },
                    )
                )
                break

            validation_error = self._validate_tool_action(action)

            if validation_error is not None:
                state.add_error(validation_error)
                run.add_step(
                    AgentStep(
                        index=run.next_step_index(),
                        step_type=AgentStepType.THINK,
                        content="Агент выбрал недопустимый инструмент.",
                        metadata={
                            "error": validation_error,
                            "action": action.to_dict(),
                        },
                    )
                )
                continue

            if self._is_duplicate_tool_call(state, action):
                error = "Повторный вызов инструмента с теми же аргументами."
                state.add_error(error)
                run.add_step(
                    AgentStep(
                        index=run.next_step_index(),
                        step_type=AgentStepType.THINK,
                        content="Повторный вызов инструмента пропущен.",
                        metadata={
                            "error": error,
                            "action": action.to_dict(),
                        },
                    )
                )
                continue

            tool_output = await self._run_tool_input(
                run=run,
                tool_input=AgentToolInput(
                    tool_name=action.tool_name or "",
                    arguments=action.arguments,
                    metadata={
                        **request.metadata,
                        "adaptive_tool_call": True,
                        "reason": action.reason,
                        "expected_result": action.expected_result,
                    },
                ),
                reason=action.reason,
            )

            state.add_tool_call(
                action=action,
                output=tool_output,
            )
            adaptive_outputs.append(tool_output)

        return adaptive_outputs

    async def _run_tool_input(
        self,
        run: AgentRun,
        tool_input: AgentToolInput,
        reason: str,
    ) -> AgentToolOutput:
        run.add_step(
            AgentStep(
                index=run.next_step_index(),
                step_type=AgentStepType.TOOL_CALL,
                content=f"Вызов инструмента: {tool_input.tool_name}",
                tool_call=AgentToolCall(
                    tool_name=tool_input.tool_name,
                    arguments=tool_input.arguments,
                ),
                metadata={
                    "tool_name": tool_input.tool_name,
                    "reason": reason,
                },
            )
        )

        try:
            tool_output = await self._tool_registry.run(tool_input)
        except Exception as exc:
            tool_output = AgentToolOutput(
                tool_name=tool_input.tool_name,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        run.add_step(
            AgentStep(
                index=run.next_step_index(),
                step_type=AgentStepType.TOOL_RESULT,
                content=self._build_tool_result_summary(tool_output),
                tool_result=AgentToolResult(
                    tool_name=tool_output.tool_name,
                    ok=tool_output.ok,
                    data=tool_output.data,
                    error=tool_output.error,
                    metadata=tool_output.metadata,
                ),
                metadata={
                    "tool_name": tool_output.tool_name,
                    "ok": tool_output.ok,
                    "reason": reason,
                },
            )
        )

        return tool_output

    def _add_previous_tool_outputs_to_state(
        self,
        state: AgentLoopState,
        tool_outputs: list[AgentToolOutput],
    ) -> None:
        for tool_output in tool_outputs:
            state.tool_calls.append(
                AgentLoopToolCall(
                    tool_name=tool_output.tool_name,
                    arguments={},
                    reason="Обязательный инструмент был вызван до adaptive loop.",
                    output=tool_output,
                )
            )

    def _validate_tool_action(
        self,
        action: AgentAction,
    ) -> str | None:
        if action.tool_name is None or not action.tool_name.strip():
            return "tool_call action must contain tool_name"

        try:
            tool = self._tool_registry.get(action.tool_name)
        except ValueError as exc:
            return str(exc)

        if not tool.spec.can_be_called_by_agent:
            return f"Tool {action.tool_name} cannot be called by agent"

        return None

    def _is_duplicate_tool_call(
        self,
        state: AgentLoopState,
        action: AgentAction,
    ) -> bool:
        if action.tool_name is None:
            return False

        action_arguments = self._stable_json(action.arguments)

        for tool_call in state.tool_calls:
            if tool_call.tool_name != action.tool_name:
                continue

            if self._stable_json(tool_call.arguments) == action_arguments:
                return True

        return False

    async def _extract_evidence(
        self,
        run: AgentRun,
        request: AgentRunRequest,
        tool_outputs: list[AgentToolOutput],
    ) -> AgentEvidenceSet:
        if not request.extract_evidence:
            return AgentEvidenceSet()

        if not tool_outputs:
            return AgentEvidenceSet()

        evidence_set = await self._evidence_extractor.extract(
            EvidenceExtractionRequest(
                goal=request.goal,
                tool_outputs=tool_outputs,
                provider_name=request.provider_name,
                metadata={
                    **request.metadata,
                    "agent_request": True,
                },
            )
        )

        run.add_step(
            AgentStep(
                index=run.next_step_index(),
                step_type=AgentStepType.THINK,
                content="Из результатов инструментов извлечены проверяемые факты.",
                metadata={
                    "evidence_count": len(evidence_set.items),
                    "verified_count": len(evidence_set.verified_items()),
                    "unverified_count": len(evidence_set.unverified_items()),
                    "conflicted_count": len(evidence_set.conflicted_items()),
                },
            )
        )

        return evidence_set

    def _build_initial_plan(
        self,
        request: AgentRunRequest,
    ) -> AgentPlan:
        steps = [
            "Понять задачу пользователя.",
        ]

        if request.required_tools:
            steps.append("Вызвать обязательные инструменты и собрать результаты.")

        if request.adaptive_tools:
            steps.append("Адаптивно выбрать дополнительные инструменты при необходимости.")

        if request.extract_evidence:
            steps.append("Извлечь проверяемые факты и источники.")

        steps.extend(
            [
                "Определить, каких данных не хватает.",
                "Сформировать итоговый ответ.",
            ]
        )

        return AgentPlan(
            goal=request.goal,
            steps=steps,
            metadata={
                "source": "local_agent_runner_v6",
                "required_tools": [
                    tool_input.tool_name
                    for tool_input in request.required_tools
                ],
                "extract_evidence": request.extract_evidence,
                "adaptive_tools": request.adaptive_tools,
                "custom_final_prompt": request.final_prompt is not None,
                "custom_final_prompt_builder": request.final_prompt_builder is not None,
                "final_response_format": request.final_response_format,
            },
        )

    def _build_action_selection_instructions(self) -> str:
        return (
            "Ты выбираешь только следующее действие агента. "
            "Верни строго один JSON-объект без markdown. "
            "Не пиши пояснений вне JSON. "
            "Не выдумывай факты. "
            "Если нужно проверить ссылку — выбери URL-инструмент. "
            "Если нужно найти кандидатов — выбери search-инструмент. "
            "Если данных достаточно или инструментов больше не нужно — верни finish."
        )

    def _build_agent_instructions(self) -> str:
        return (
            "Ты работаешь как агентная прослойка внутри сервиса афиш. "
            "Используй результаты инструментов и evidence как дополнительные данные, "
            "но не считай их абсолютно истинными. "
            "Очень важное правило: в раздел 'точно известно' можно помещать только факты "
            "со статусом verified из evidence или факты, явно пришедшие из исходного пользовательского текста. "
            "Факты со статусом unverified нельзя подавать как точно подтверждённые. "
            "Если verified evidence нет, прямо напиши, что внешних подтверждённых фактов пока нет. "
            "Если URL заблокирован антиботом, напиши, что прямое чтение источника не удалось. "
            "Если официальный сайт прочитан, но не содержит нужных дат или площадок, укажи это как неподтверждение. "
            "Если данные противоречат друг другу, явно укажи конфликт. "
            "Не выдумывай даты, площадки, цены, ссылки и факты. "
            "Отвечай структурно и пригодно для дальнейшей обработки."
        )

    def _build_custom_or_default_final_prompt(
        self,
        request: AgentRunRequest,
        plan: AgentPlan,
        tool_outputs: list[AgentToolOutput],
        evidence_set: AgentEvidenceSet,
    ) -> str:
        if request.final_prompt_builder is not None:
            return request.final_prompt_builder(
                request.goal,
                plan,
                tool_outputs,
                evidence_set,
            )

        if request.final_prompt is not None:
            return request.final_prompt

        return self._build_final_prompt(
            request=request,
            plan=plan,
            tool_outputs=tool_outputs,
            evidence_set=evidence_set,
        )

    def _build_final_prompt(
        self,
        request: AgentRunRequest,
        plan: AgentPlan,
        tool_outputs: list[AgentToolOutput],
        evidence_set: AgentEvidenceSet,
    ) -> str:
        plan_text = "\n".join(
            f"{index}. {step}"
            for index, step in enumerate(plan.steps, start=1)
        )

        tool_results_text = self._build_tool_results_text(tool_outputs)
        evidence_text = self._build_evidence_text(evidence_set)
        evidence_summary_text = self._build_evidence_summary_text(evidence_set)

        return (
            "Задача агента:\n"
            f"{request.goal.strip()}\n\n"
            "Стартовый план:\n"
            f"{plan_text}\n\n"
            "Результаты инструментов:\n"
            f"{tool_results_text}\n\n"
            "Сводка evidence:\n"
            f"{evidence_summary_text}\n\n"
            "Извлечённые evidence-факты:\n"
            f"{evidence_text}\n\n"
            "Правила финального ответа:\n"
            "1. Не называй unverified-факты точно известными.\n"
            "2. Если verified evidence = 0, напиши, что внешних подтверждённых фактов пока нет.\n"
            "3. Данные из исходного текста пользователя можно вынести отдельно в раздел 'Во входном тексте'.\n"
            "4. Данные из groq_search — это кандидаты, пока они не подтверждены url_read/url_parser/db/manual_confirmed.\n"
            "5. Если url_read вернул blocked_by_antibot=true, источник не считается проверенным.\n"
            "6. Если прочитанный официальный сайт не содержит нужных дат/площадок, это неподтверждение, а не подтверждение.\n\n"
            "Выполни задачу настолько полно, насколько позволяют входные данные. "
            "Отдельно укажи: "
            "1) что есть во входном тексте пользователя, "
            "2) что найдено через инструменты, "
            "3) что удалось подтвердить через verified evidence, "
            "4) что осталось unverified, "
            "5) какие есть конфликты или неподтверждения, "
            "6) чего не хватает для полной публикации афиши."
        )

    def _build_tool_results_text(
        self,
        tool_outputs: list[AgentToolOutput],
    ) -> str:
        if not tool_outputs:
            return "Инструменты не вызывались."

        parts: list[str] = []

        for index, tool_output in enumerate(tool_outputs, start=1):
            parts.append(
                "\n".join(
                    [
                        f"{index}. Tool: {tool_output.tool_name}",
                        f"OK: {tool_output.ok}",
                        f"Error: {tool_output.error or '-'}",
                        "Data:",
                        self._compact_data(tool_output.data),
                    ]
                )
            )

        return "\n\n".join(parts)

    def _build_evidence_summary_text(
        self,
        evidence_set: AgentEvidenceSet,
    ) -> str:
        return "\n".join(
            [
                f"Total evidence: {len(evidence_set.items)}",
                f"Verified evidence: {len(evidence_set.verified_items())}",
                f"Unverified evidence: {len(evidence_set.unverified_items())}",
                f"Conflicted evidence: {len(evidence_set.conflicted_items())}",
            ]
        )

    def _build_evidence_text(
        self,
        evidence_set: AgentEvidenceSet,
    ) -> str:
        if not evidence_set.items:
            return "Evidence не извлечены."

        parts: list[str] = []

        for index, item in enumerate(evidence_set.items, start=1):
            source_url = item.source.url if item.source is not None else None
            source_title = item.source.title if item.source is not None else None

            parts.append(
                "\n".join(
                    [
                        f"{index}. Field: {item.field}",
                        f"Value: {item.value}",
                        f"Confidence: {item.confidence.value}",
                        f"Status: {item.status.value}",
                        f"Source: {source_title or '-'}",
                        f"URL: {source_url or '-'}",
                        f"Explanation: {item.explanation or '-'}",
                    ]
                )
            )

        return "\n\n".join(parts)

    def _build_tool_result_summary(
        self,
        tool_output: AgentToolOutput,
    ) -> str:
        if tool_output.ok:
            return f"Инструмент {tool_output.tool_name} успешно вернул данные."

        return (
            f"Инструмент {tool_output.tool_name} завершился ошибкой: "
            f"{tool_output.error or 'unknown error'}"
        )

    def _tool_output_to_data(
        self,
        tool_output: AgentToolOutput,
    ) -> dict[str, Any]:
        return {
            "tool_name": tool_output.tool_name,
            "ok": tool_output.ok,
            "data": tool_output.data,
            "error": tool_output.error,
            "metadata": tool_output.metadata,
        }

    def _compact_data(
        self,
        data: Any,
    ) -> str:
        if data is None:
            return "-"

        text = str(data)

        if len(text) <= 4000:
            return text

        return text[:4000] + "\n...[truncated]"

    def _stable_json(
        self,
        value: Any,
    ) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        