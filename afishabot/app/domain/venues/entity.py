from dataclasses import dataclass
from datetime import datetime

from ...core.types.ids import VenueID, CityID

@dataclass
class Venue:
    id: VenueID | None = None

    name: str = ""

    city_id: CityID | None = None

    description: str | None = None
    
    address: str | None = None 
    latitude: float | None = None
    longitude: float | None = None
    
    capacity: int | None = None
    
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
