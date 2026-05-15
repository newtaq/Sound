from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.common.uow import UnitOfWork
from app.infrastructure.db.repositories.event_repository import SQLAlchemyEventRepository


class SQLAlchemyUnitOfWork(UnitOfWork):
    def __inti(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self.session: AsyncSession | None = None
        self.events: SQLAlchemyEventRepository | None = None
        
    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        self.session = self.session_factory()
        self.events = SQLAlchemyEventRepository(self.session)    
        await self.begin()
        return self 
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.session is None:
            return 
        
        if exc_type is not None:
            await self.rollback()
            
        await self.session.close()
        
    async def begin(self) -> None:
        if self.session is None:
            raise RuntimeError("Session is not initialized.")
        
        await self.session.begin()
        
        
    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("Session is not initialized.")
        
        await self.session.commit()
        
        
    async def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("Session is not initialized.")
        
        await self.session.rollback()
        
