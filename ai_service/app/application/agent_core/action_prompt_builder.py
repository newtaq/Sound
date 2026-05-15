import json
from typing import Any

from app.application.agent_core.loop_state import AgentLoopState


class AgentActionPromptBuilder:
    def build_next_action_prompt(
        self,
        state: AgentLoopState,
    ) -> str:
        state_data = self._prepare_state_data(state)

        return (
            "Ты управляешь следующим шагом AI-агента.\n\n"
            "Тебе нужно выбрать только одно действие:\n"
            "1. Вызвать инструмент.\n"
            "2. Завершить работу.\n\n"
            "Ответ должен быть строго JSON без markdown и без пояснений вокруг.\n\n"
            "Формат для вызова инструмента:\n"
            "{\n"
            '  "action_type": "tool_call",\n'
            '  "tool_name": "название_инструмента",\n'
            '  "arguments": {},\n'
            '  "reason": "зачем нужен этот инструмент",\n'
            '  "expected_result": "что ожидаешь получить"\n'
            "}\n\n"
            "Формат для завершения:\n"
            "{\n"
            '  "action_type": "finish",\n'
            '  "reason": "почему можно завершить работу"\n'
            "}\n\n"
            "Правила:\n"
            "- вызывай только инструменты из available_tools;\n"
            "- не вызывай инструмент повторно с теми же аргументами без причины;\n"
            "- если данных достаточно или шаги закончились, верни finish;\n"
            "- search-инструменты дают только кандидатов, а не проверенные факты;\n"
            "- для проверки ссылок используй URL-инструменты;\n"
            "- если есть ошибки инструментов, учитывай их и не зацикливайся;\n"
            "- не выдумывай факты, даты, площадки, адреса и ссылки.\n\n"
            "Текущее состояние агента:\n"
            f"{json.dumps(state_data, ensure_ascii=False, indent=2)}"
        )

    def _prepare_state_data(
        self,
        state: AgentLoopState,
    ) -> dict[str, Any]:
        data = state.to_prompt_data()

        data["remaining_steps"] = max(
            state.max_steps - state.step_count,
            0,
        )

        return data
    


