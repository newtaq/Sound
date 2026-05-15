from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.application.events.repository import EventRepository
from app.core.types.ids import EventID
from app.infrastructure.db.models import EventModel
from app.infrastructure.db.mappers import EventMapper
from app.domain.events import Event

from app.domain.events.enums import EventStatus, EventType
from app.core.types.ids import VenueID

class SQLAlchemyEventRepository(EventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        
    async def get(self, event_id: EventID) -> Event | None:
        result = await self.session.execute(
            select(EventModel).where(EventModel.id == event_id)
        )
        event_model = result.scalar_one_or_none()
        
        if event_model is None:
            return None
        
        return EventMapper.to_entity(event_model)

    async def create(self, event: Event) ->  Event:
        event_model = EventMapper.to_model(event)
        
        self.session.add(event_model)
        await self.session.flush()
        await self.session.refresh(event_model)

        return EventMapper.to_entity(event_model)

    async def update(self, event: Event) -> Event | None:
        result = await self.session.execute(
            select(EventModel).where(EventModel.id == event.id)
        )
        event_model = result.scalar_one_or_none()
        
        if event_model is None:
            return None 
        
        EventMapper.update_model_from_entity(event_model, event)

        await self.session.flush()
        await self.session.refresh(event_model)
        
        return EventMapper.to_entity(event_model)
        
        
    async def delete(self, event_id: EventID) -> bool:
        result = await self.session.execute(
            select(EventModel).where(EventModel.id == event_id)
        )
        event_model = result.scalar_one_or_none()
        
        if event_model is None:
            return False

        await self.session.delete(event_model)
        await self.session.flush()

        return True

    async def list(
        self,
        *,
        status: EventStatus | None = None,
        event_type: EventType | None = None,
        venue_id: VenueID | None = None,
        limit: int | None = None,
        offset: int | None = None,
        ) -> list[Event]:
        stmt = select(EventModel)
        
        if status is not None:
            stmt = stmt.where(
                EventModel.status == status.value
                )
        if event_type is not None:
            stmt = stmt.where(
                EventModel.event_type == event_type.value
            )
        
        if venue_id is not None:
            stmt = stmt.where(
                EventModel.venue_id == int(venue_id)
                )
            
        stmt = stmt.limit(limit) if limit is not None else stmt
        
        stmt = stmt.offset(offset) if offset is not None else stmt

        result = await self.session.execute(stmt)

        event_models = result.scalars().all()
        
        return [
            EventMapper.to_entity(event_model) for event_model in event_models
        ]
        
