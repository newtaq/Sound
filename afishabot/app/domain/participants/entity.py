from dataclasses import dataclass, field
from datetime import datetime 

from ...core.types.ids import ParticipantID

@dataclass
class Participant:
    id: ParticipantID | None = None
    name: str = ""
    
    aliases: list[str] = field(default_factory=list)
    
    emoji: str | None = None

    description: str | None = None 
    
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
