import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.application.ai_service import AIService
from app.application.ai_sessions import (
    AIConversationStore,
    MemoryAIConversationStore,
    build_assistant_message,
    build_user_message,
)
from app.application.contracts import (
    AIMedia,
    AIMode,
    AIRequest,
    AIResponse,
    AIResponseStatus,
    AIStreamChunk,
    AITextFile,
)


class _SessionIdNotProvided:
    pass


_SESSION_ID_NOT_PROVIDED = _SessionIdNotProvided()

SessionIdInput = str | None | _SessionIdNotProvided


@dataclass(slots=True)
class AIClientRequestOptions:
    session_id: SessionIdInput = _SESSION_ID_NOT_PROVIDED
    create_session: bool | None = None
    provider_name: str | None = None
    mode: AIMode = AIMode.DEEP
    instructions: str | None = None
    response_format: str = "plain_text"
    media: list[AIMedia] = field(default_factory=list)
    text_files: list[AITextFile] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    use_history: bool | None = None
    save_history: bool | None = None
    history_limit: int | None = None


class AIClient:
    def __init__(
        self,
        service: AIService,
        conversation_store: AIConversationStore | None = None,
        use_history_by_default: bool | None = None,
        save_history_by_default: bool | None = None,
        history_limit: int | None = None,
    ) -> None:
        self._service = service
        self._conversation_store = conversation_store or MemoryAIConversationStore()
        self._use_history_by_default = (
            use_history_by_default
            if use_history_by_default is not None
            else self._read_bool_env(
                "AI_CLIENT_USE_HISTORY_BY_DEFAULT",
                False,
            )
        )
        self._save_history_by_default = (
            save_history_by_default
            if save_history_by_default is not None
            else self._read_bool_env(
                "AI_CLIENT_SAVE_HISTORY_BY_DEFAULT",
                True,
            )
        )
        self._history_limit = (
            history_limit
            if history_limit is not None
            else self._read_int_env(
                "AI_CLIENT_HISTORY_LIMIT",
                20,
            )
        )

    async def ask(
        self,
        text: str,
        session_id: SessionIdInput = _SESSION_ID_NOT_PROVIDED,
        create_session: bool | None = None,
        provider_name: str | None = None,
        mode: AIMode = AIMode.DEEP,
        instructions: str | None = None,
        response_format: str = "plain_text",
        media: list[AIMedia] | None = None,
        text_files: list[AITextFile] | None = None,
        metadata: dict[str, Any] | None = None,
        use_history: bool | None = None,
        save_history: bool | None = None,
        history_limit: int | None = None,
    ) -> AIResponse:
        resolved_session_id = self._resolve_session_id(
            session_id=session_id,
            create_session=create_session,
        )
        resolved_use_history = self._resolve_use_history(use_history)
        resolved_save_history = self._resolve_save_history(save_history)
        resolved_history_limit = self._resolve_history_limit(history_limit)

        request = AIRequest(
            text=text,
            session_id=resolved_session_id,
            provider_name=provider_name,
            mode=mode,
            instructions=instructions,
            response_format=response_format,
            media=media or [],
            text_files=text_files or [],
            metadata=metadata or {},
        )

        if resolved_use_history and request.session_id is not None:
            request.history = await self._conversation_store.get_messages(
                session_id=request.session_id,
                limit=resolved_history_limit,
            )

        response = await self._service.generate(request)

        if (
            resolved_save_history
            and response.status == AIResponseStatus.OK
            and request.session_id is not None
        ):
            await self._conversation_store.add_message(
                session_id=request.session_id,
                message=build_user_message(text),
            )
            await self._conversation_store.add_message(
                session_id=request.session_id,
                message=build_assistant_message(response.text),
            )

        return response

    async def ask_with_options(
        self,
        text: str,
        options: AIClientRequestOptions | None = None,
    ) -> AIResponse:
        options = options or AIClientRequestOptions()

        return await self.ask(
            text=text,
            session_id=options.session_id,
            create_session=options.create_session,
            provider_name=options.provider_name,
            mode=options.mode,
            instructions=options.instructions,
            response_format=options.response_format,
            media=options.media,
            text_files=options.text_files,
            metadata=options.metadata,
            use_history=options.use_history,
            save_history=options.save_history,
            history_limit=options.history_limit,
        )

    def stream(
        self,
        text: str,
        session_id: SessionIdInput = _SESSION_ID_NOT_PROVIDED,
        create_session: bool | None = None,
        provider_name: str | None = None,
        mode: AIMode = AIMode.DEEP,
        instructions: str | None = None,
        response_format: str = "plain_text",
        media: list[AIMedia] | None = None,
        text_files: list[AITextFile] | None = None,
        metadata: dict[str, Any] | None = None,
        use_history: bool | None = None,
        history_limit: int | None = None,
    ) -> AsyncIterator[AIStreamChunk]:
        resolved_session_id = self._resolve_session_id(
            session_id=session_id,
            create_session=create_session,
        )

        request = AIRequest(
            text=text,
            session_id=resolved_session_id,
            provider_name=provider_name,
            mode=mode,
            instructions=instructions,
            response_format=response_format,
            media=media or [],
            text_files=text_files or [],
            metadata=metadata or {},
        )

        return self._service.stream(request)

    async def get_history(
        self,
        session_id: str,
        limit: int | None = None,
    ):
        return await self._conversation_store.get_messages(
            session_id=session_id,
            limit=limit,
        )

    async def clear_history(
        self,
        session_id: str,
    ) -> None:
        await self._conversation_store.clear(session_id)

    def _resolve_session_id(
        self,
        session_id: SessionIdInput,
        create_session: bool | None,
    ) -> str | None:
        if isinstance(session_id, _SessionIdNotProvided):
            if create_session is False:
                return None

            return self._build_session_id()

        return session_id

    def _resolve_use_history(
        self,
        value: bool | None,
    ) -> bool:
        if value is None:
            return self._use_history_by_default

        return value

    def _resolve_save_history(
        self,
        value: bool | None,
    ) -> bool:
        if value is None:
            return self._save_history_by_default

        return value

    def _resolve_history_limit(
        self,
        value: int | None,
    ) -> int | None:
        if value is None:
            return self._history_limit

        return value

    def _build_session_id(self) -> str:
        return f"session_{uuid4().hex}"

    def _read_bool_env(
        self,
        name: str,
        default: bool,
    ) -> bool:
        value = os.getenv(name)

        if value is None:
            return default

        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    def _read_int_env(
        self,
        name: str,
        default: int | None,
    ) -> int | None:
        value = os.getenv(name)

        if value is None:
            return default

        try:
            return int(value)
        except ValueError:
            return default
        

