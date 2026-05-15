from dataclasses import dataclass
from datetime import datetime

from ...core.types.ids import CountryID


@dataclass
class Country:
    id: CountryID | None = None
    name: str = ""
    
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
