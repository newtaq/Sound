from dataclasses import dataclass
from datetime import datetime

from .enums import Currency
from ...core.types.ids import PromoCodeID, TicketOfferID


@dataclass
class PromoCode:
    id: PromoCodeID | None = None 
    tickets_offer_id: TicketOfferID | None = None
    
    code: str = ""
    
    discount_percent: float | None = None 
    discount_amount: float | None = None
    currency: Currency = Currency.RUB
    
    discount_text: str | None = None 
    
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool = True
    
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
