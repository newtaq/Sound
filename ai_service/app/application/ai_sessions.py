from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field

from app.application.contracts import AIMessage, AIMessageRole


class AIConversationStore(ABC):
    @abstractmethod
    async def get_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[AIMessage]:
        raise NotImplementedError

    @abstractmethod
    async def add_message(
        self,
        session_id: str,
        message: AIMessage,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def clear(
        self,
        session_id: str,
    ) -> None:
        raise NotImplementedError


@dataclass(slots=True)
class MemoryAIConversationStore(AIConversationStore):
    max_messages_per_session: int = 40
    _messages: dict[str, list[AIMessage]] = field(
        default_factory=lambda: defaultdict(list),
    )

    async def get_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[AIMessage]:
        messages = list(self._messages.get(session_id, []))

        if limit is None:
            return messages

        if limit <= 0:
            return []

        return messages[-limit:]

    async def add_message(
        self,
        session_id: str,
        message: AIMessage,
    ) -> None:
        messages = self._messages.setdefault(session_id, [])
        messages.append(message)

        if len(messages) > self.max_messages_per_session:
            del messages[:-self.max_messages_per_session]

    async def clear(
        self,
        session_id: str,
    ) -> None:
        self._messages.pop(session_id, None)


def build_user_message(
    text: str,
) -> AIMessage:
    return AIMessage(
        role=AIMessageRole.USER,
        content=text,
    )


def build_assistant_message(
    text: str,
) -> AIMessage:
    return AIMessage(
        role=AIMessageRole.ASSISTANT,
        content=text,
    )
    

