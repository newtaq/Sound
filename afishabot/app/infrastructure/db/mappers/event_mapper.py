from app.domain.events import Event
from app.domain.events.enums import AgeRating, EventStatus, EventType
from app.infrastructure.db.models import EventModel
from app.core.types.ids import *


class EventMapper:
    @staticmethod
    def to_entity(model: EventModel) -> Event:
        return Event(
            id=EventID(model.id),
            title=model.title,
            description=model.description,
            age_rating=AgeRating(model.age_rating) if model.age_rating is not None else None,
            event_type=EventType(model.event_type) if model.event_type is not None else None,
            tour_id=TourID(model.tour_id) if model.tour_id is not None else None,
            status=EventStatus(model.status),
            venue_id=VenueID(model.venue_id) if model.venue_id is not None else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(event: Event) -> EventModel:
        return EventModel(
            id=int(event.id) if event.id is not None else None,
            title=event.title,
            description=event.description,
            age_rating=int(event.age_rating) if event.age_rating is not None else None,
            event_type=event.event_type.value if event.event_type is not None else None,
            tour_id=int(event.tour_id) if event.tour_id is not None else None,
            status=event.status.value,
            venue_id=int(event.venue_id) if event.venue_id is not None else None,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )

    @staticmethod
    def update_model_from_entity(model: EventModel, event: Event) -> EventModel:
        model.title = event.title
        model.description = event.description
        model.age_rating = int(event.age_rating) if event.age_rating is not None else None
        model.event_type = event.event_type.value if event.event_type is not None else None
        model.tour_id = int(event.tour_id) if event.tour_id is not None else None
        model.status = event.status.value
        model.venue_id = int(event.venue_id) if event.venue_id is not None else None
        return model
    
