from abc import ABC, abstractmethod

from app.application.events.repository import EventRepository

class UnitOfWork(ABC):
    events: EventRepository
    
    @abstractmethod
    async def __aenter__(self) -> None:
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
    
    @abstractmethod
    async def begin(self) -> None:
        pass
    
    @abstractmethod
    async def commit(self) -> None:
        pass
    
    @abstractmethod
    async def rollback(self) -> None:
        pass
    
    
    
