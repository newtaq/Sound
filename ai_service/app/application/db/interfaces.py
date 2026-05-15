from abc import ABC, abstractmethod
from typing import Any


class AIDatabaseGateway(ABC):
    @abstractmethod
    async def search_context(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def save_analysis_result(self, result: dict[str, Any]) -> None:
        raise NotImplementedError
    

