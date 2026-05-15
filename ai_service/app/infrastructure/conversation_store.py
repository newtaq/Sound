import json
import os
import re
from pathlib import Path

from app.application.ai_sessions import (
    AIConversationStore,
    MemoryAIConversationStore,
)
from app.application.contracts import AIMessage, AIMessageRole
from app.infrastructure.env import load_env_file


class FileAIConversationStore(AIConversationStore):
    def __init__(
        self,
        directory: str | Path = ".runtime/ai_sessions",
        max_messages_per_session: int = 40,
    ) -> None:
        self._directory = Path(directory)
        self._max_messages_per_session = max_messages_per_session
        self._directory.mkdir(parents=True, exist_ok=True)

    async def get_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[AIMessage]:
        messages = self._read_messages(session_id)

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
        messages = self._read_messages(session_id)
        messages.append(message)

        if len(messages) > self._max_messages_per_session:
            messages = messages[-self._max_messages_per_session:]

        self._write_messages(session_id, messages)

    async def clear(
        self,
        session_id: str,
    ) -> None:
        path = self._get_session_path(session_id)

        if path.exists():
            path.unlink()

    def _read_messages(self, session_id: str) -> list[AIMessage]:
        path = self._get_session_path(session_id)

        if not path.exists():
            return []

        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(raw_data, list):
            return []

        messages: list[AIMessage] = []

        for item in raw_data:
            if not isinstance(item, dict):
                continue

            role = self._parse_role(item.get("role"))
            content = item.get("content")

            if role is None or not isinstance(content, str):
                continue

            messages.append(
                AIMessage(
                    role=role,
                    content=content,
                )
            )

        return messages

    def _write_messages(
        self,
        session_id: str,
        messages: list[AIMessage],
    ) -> None:
        path = self._get_session_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = [
            {
                "role": self._role_to_string(message.role),
                "content": message.content,
            }
            for message in messages
        ]

        temp_path = path.with_suffix(".tmp")

        temp_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temp_path.replace(path)

    def _get_session_path(self, session_id: str) -> Path:
        safe_session_id = self._safe_session_id(session_id)
        return self._directory / f"{safe_session_id}.json"

    def _safe_session_id(self, session_id: str) -> str:
        value = session_id.strip()

        if not value:
            return "empty_session"

        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)

    def _parse_role(self, value: object) -> AIMessageRole | None:
        if not isinstance(value, str):
            return None

        try:
            return AIMessageRole(value)
        except ValueError:
            return None

    def _role_to_string(self, role: AIMessageRole) -> str:
        value = getattr(role, "value", None)

        if isinstance(value, str):
            return value

        return str(role)


def build_conversation_store() -> AIConversationStore:
    load_env_file()

    store_type = os.getenv("AI_CONVERSATION_STORE", "file").strip().lower()

    max_messages = _read_int(
        "AI_CONVERSATION_MAX_MESSAGES_PER_SESSION",
        40,
    )

    if store_type == "memory":
        return MemoryAIConversationStore(
            max_messages_per_session=max_messages,
        )

    directory = os.getenv(
        "AI_CONVERSATION_STORE_DIR",
        ".runtime/ai_sessions",
    )

    return FileAIConversationStore(
        directory=directory,
        max_messages_per_session=max_messages,
    )


def _read_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default
    

