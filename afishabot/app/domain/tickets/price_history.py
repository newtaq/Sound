from dataclasses import dataclass
from datetime import datetime

from .enums import Currency
from ...core.types.ids import PriceHistoryEntryID, TicketOfferID


@dataclass
class PriceHistoryEntry:
    id: PriceHistoryEntryID | None = None
    tickets_offer_id: TicketOfferID | None = None

    price: int = 0
    currency: Currency = Currency.RUB
    
    recorded_at: datetime | None = None
    
    
