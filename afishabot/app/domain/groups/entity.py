from dataclasses import dataclass, field

from ..participants import Participant
from ..artists import Artist
from ...core.types.ids import GroupID 


@dataclass
class Group(Participant):
    id: GroupID | None = None
    members: list[Artist] = field(default_factory=list)
    
