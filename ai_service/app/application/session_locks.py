import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class AISessionLockManager:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def lock(self, session_id: str | None) -> AsyncIterator[None]:
        if session_id is None:
            yield
            return

        lock = self._locks.setdefault(session_id, asyncio.Lock())

        async with lock:
            yield
            

