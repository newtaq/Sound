from dataclasses import dataclass
from datetime import datetime

from ...core.types.ids import OccurrenceID


@dataclass
class EventOccurrence:
    id: OccurrenceID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None  
    
