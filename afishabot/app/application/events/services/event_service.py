from app.application.events.repository import EventRepository
from app.core.types.ids import EventID, VenueID, TourID
from app.domain.events import Event 
from app.domain.events.enums import EventStatus, EventType, AgeRating


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self.repository = repository 
        
    async def get_event(self, event_id: EventID) -> Event | None:
        return await self.repository.get(event_id)
    
    async def create_event(
        self,
        *,
        title: str,
        description: str | None,
        age_rating: AgeRating | None,
        event_type: EventType | None,
        tour_id: TourID | None,
        venue_id: VenueID | None,
    ) -> Event:
        event = Event(
            id=None,
            title=title,
            description=description,
            age_rating=age_rating,
            event_type=event_type,
            tour_id=tour_id,
            status=EventStatus.DRAFT,
            venue_id=venue_id,
            created_at=None,
            updated_at=None,
        )
            
        return await self.repository.create(event)
        
    async def update_event(self, event: Event) -> Event | None:
        if event.id is None:
            raise ValueError("Event ID must be provided for update.")
        
        existing_event = await self.repository.get(event.id)
        
        if existing_event is None:
            return None
        
        
        return await self.repository.update(event)
    
    
    async def delete_event(self, event_id: EventID) -> bool:        
        return await self.repository.delete(event_id)
    
    async def list_events(
        self,
        *,
        status: EventStatus | None = None,
        event_type: EventType | None = None,
        venue_id: VenueID | None = None,
        limit: int | None = None,
        offset: int | None = None
    ) -> list[Event]:
        return await self.repository.list(
            status=status,
            event_type=event_type,
            venue_id=venue_id,
            limit=limit,
            offset=offset
        )
        
