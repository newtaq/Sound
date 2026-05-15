from dataclasses import dataclass
from datetime import datetime

from ...core.types.ids import TicketOfferID, EventID


@dataclass
class TicketOffer:
    id: TicketOfferID | None = None
    event_id: EventID | None = None

    url: str = ""
    
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
