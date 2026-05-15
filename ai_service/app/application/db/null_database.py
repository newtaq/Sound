from typing import Any

from app.application.db.interfaces import AIDatabaseGateway


class NullAIDatabaseGateway(AIDatabaseGateway):
    async def search_context(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return []

    async def save_analysis_result(self, result: dict[str, Any]) -> None:
        return None
    

