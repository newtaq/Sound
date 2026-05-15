from dataclasses import dataclass, field
from datetime import datetime

from .occurrence import EventOccurrence
from .enums import AgeRating, EventStatus, EventType, Genre
from ..participants import Participant  
from ..tickets import TicketOffer   
from ..organizers import Organizer
from ...core.types.ids import EventID, VenueID, TourID


@dataclass
class Event:
    id: EventID | None = None
    title: str = ""
    description: str | None = None  
    age_rating: AgeRating | None = None
    event_type: EventType | None = None
    genres: list[Genre] = field(default_factory=list)
    tour_id: TourID | None = None
    status: EventStatus = EventStatus.DRAFT

    venue_id: VenueID | None = None
    occurrences: list[EventOccurrence] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)
    organizers: list[Organizer] = field(default_factory=list)
    ticket_offers: list[TicketOffer] = field(default_factory=list)
    
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
