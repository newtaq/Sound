from dataclasses import dataclass

from ..participants import Participant
from ...core.types.ids import ArtistID, CountryID

@dataclass
class Artist(Participant):
    id: ArtistID | None = None
    country_id: CountryID | None = None

    is_foreign_agent: bool = False
    
