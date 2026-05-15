from dataclasses import dataclass 
from datetime import datetime

from ...core.types.ids import CityID, CountryID


@dataclass
class City:
    id: CityID | None = None
    name: str = ""
    country_id: CountryID | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

