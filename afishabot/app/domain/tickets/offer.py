from dataclasses import dataclass
from dis import disco


@dataclass
class TicketOffer:
    id: int | None = None
    
    event_id: int | None = None
    
    url: str = ""
    
    price_from: float | None = None
    price_to: float | None = None
    currency: str | None = None
    
    promo_code: str | None = None
    discount_text: str | None = None
