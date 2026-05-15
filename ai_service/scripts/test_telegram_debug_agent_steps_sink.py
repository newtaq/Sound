from app.application.agent_core.models import (
    AgentFinalResult,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepType,
    AgentToolCall,
    AgentToolResult,
)
from app.infrastructure.telegram_debug.agent_steps_sink import TelegramAgentRunDebugSink
from app.infrastructure.telegram_debug.config import TelegramVisualDebugConfig
from app.infrastructure.telegram_debug.models import (
    TelegramDebugMessage,
    TelegramDebugMessageKind,
)


class FakeTelegramSink:
    def __init__(self) -> None:
        self.messages: list[TelegramDebugMessage] = []

    def emit_background(
        self,
        message: TelegramDebugMessage,
    ) -> None:
        self.messages.append(message)


def main() -> None:
    fake_sink = FakeTelegramSink()

    sink = TelegramAgentRunDebugSink(
        config=TelegramVisualDebugConfig(
            enabled=True,
            bot_token="fake",
            chat_id=-100123,
        ),
        telegram_sink=fake_sink,
    )

    run = AgentRun(
        session_id="session-1",
        request_id="request-1",
        status=AgentRunStatus.FINISHED,
        goal="Собери афишу",
        metadata={
            "provider_name": "groq",
            "event_title": "КИШЛАК",
            "event_date": "12.05.2026",
            "poster_agent_review_text": " Черновик афиши: нужна проверка\n\nНазвание: КИШЛАК",
        },
    )

    run.add_step(
        AgentStep(
            index=1,
            step_type=AgentStepType.THINK,
            content="Понять задачу.",
            metadata={"phase": "plan"},
        )
    )
    run.add_step(
        AgentStep(
            index=2,
            step_type=AgentStepType.TOOL_CALL,
            content="Вызов инструмента: groq_search",
            tool_call=AgentToolCall(
                tool_name="groq_search",
                arguments={"query": "КИШЛАК 12.05.2026"},
            ),
        )
    )
    run.add_step(
        AgentStep(
            index=3,
            step_type=AgentStepType.TOOL_RESULT,
            content="Инструмент groq_search успешно вернул данные.",
            tool_result=AgentToolResult(
                tool_name="groq_search",
                ok=True,
                data={"text": "source"},
            ),
        )
    )
    run.add_step(
        AgentStep(
            index=4,
            step_type=AgentStepType.FINAL,
            content='```json\n{"ok": true}\n```',
        )
    )

    run.final_result = AgentFinalResult(
        text="Финальный ответ агента.",
        structured_data={"ok": True},
    )

    sink.emit_agent_run(run)

    assert len(fake_sink.messages) == 4

    first = fake_sink.messages[0]
    assert first.kind == TelegramDebugMessageKind.INFO
    assert first.session_id == "session-1"
    assert first.request_id == "request-1"
    assert first.provider_name == "groq"
    assert first.event_title == "КИШЛАК"
    assert "THINK #1/4" in first.text
    assert first.metadata["agent_step"] is True
    assert first.metadata["step_type"] == "think"
    assert first.metadata["status"] == "finished"
    assert first.metadata["event_date"] == "12.05.2026"

    second = fake_sink.messages[1]
    assert second.kind == TelegramDebugMessageKind.TOOL_CALL
    assert second.metadata["tool_call"]["tool_name"] == "groq_search"

    third = fake_sink.messages[2]
    assert third.kind == TelegramDebugMessageKind.TOOL_RESULT
    assert third.metadata["tool_result"]["ok"] is True

    final = fake_sink.messages[3]
    assert final.kind == TelegramDebugMessageKind.INFO
    assert "FINAL #4/4" in final.text
    assert "```json" not in final.text
    assert final.metadata["status"] == "finished"
    assert final.metadata["summary_ready"] is True
    assert "Название:" in final.text

    print("ok")


if __name__ == "__main__":
    main()
