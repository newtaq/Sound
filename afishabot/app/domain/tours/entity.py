from dataclasses import dataclass
from datetime import datetime

from ...core.types.ids import TourID


@dataclass
class Tour:
    id: TourID | None = None
    name: str = ""
    description: str | None = None
    
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
