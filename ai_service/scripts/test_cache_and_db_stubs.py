import asyncio

from app.application.cache import MemoryAICacheStore
from app.application.db import NullAIDatabaseGateway


async def main() -> None:
    cache = MemoryAICacheStore()

    await cache.set("test:key", {"value": 123})
    cached_value = await cache.get("test:key")

    await cache.delete("test:key")
    deleted_value = await cache.get("test:key")

    db = NullAIDatabaseGateway()

    context = await db.search_context("Кишлак тур 2026", limit=5)
    await db.save_analysis_result(
        {
            "content_type": "tour_announcement",
            "main_decision": "create_tour_candidate",
        }
    )

    print("CACHE VALUE:", cached_value)
    print("DELETED VALUE:", deleted_value)
    print("DB CONTEXT:", context)
    print("DB SAVE: ok")


if __name__ == "__main__":
    asyncio.run(main())
    
