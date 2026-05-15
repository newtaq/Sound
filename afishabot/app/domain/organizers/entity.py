from dataclasses import dataclass

from ..participants import Participant
from ...core.types.ids import OrganizerID


@dataclass
class Organizer(Participant):
    id: OrganizerID | None = None
    website: str | None = None
    telegram_channel_id: str | None = None
    
