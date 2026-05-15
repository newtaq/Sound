import time
from dataclasses import dataclass
from typing import Any

from app.application.cache.interfaces import AICacheStore


@dataclass(slots=True)
class _MemoryCacheItem:
    value: Any
    expires_at: float | None = None


class MemoryAICacheStore(AICacheStore):
    def __init__(self) -> None:
        self._items: dict[str, _MemoryCacheItem] = {}

    async def get(self, key: str) -> Any | None:
        item = self._items.get(key)

        if item is None:
            return None

        if item.expires_at is not None and item.expires_at <= time.time():
            await self.delete(key)
            return None

        return item.value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at = None
        if ttl_seconds is not None:
            expires_at = time.time() + ttl_seconds

        self._items[key] = _MemoryCacheItem(
            value=value,
            expires_at=expires_at,
        )

    async def delete(self, key: str) -> None:
        self._items.pop(key, None)
        

