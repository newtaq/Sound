from typing import Protocol

from app.core.types.ids import EventID, VenueID
from app.domain.events.entity import Event
from app.domain.events.enums import EventStatus, EventType

class EventRepository(Protocol):
    async def get(self, event_id: EventID) -> Event | None:
        ...
        
    async def create(self, event: Event) -> Event:
        ...
    
    async def update(self, event: Event) -> Event | None:
        ...
            
    async def delete(self, event_id: EventID) -> bool:
        ...
        
    async def list(
        self,
        *,
        status: EventStatus | None = None,
        event_type: EventType | None = None,
        venue_id: VenueID | None = None,
        limit: int | None = None,
        offset: int | None = None
        ) -> list[Event]:
        ...
        
        
