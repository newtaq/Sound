from __future__ import annotations

from enum import StrEnum


class MessageKind(StrEnum):
    EVENT = "event"
    PROMO = "promo"
    GIVEAWAY = "giveaway"
    DIGEST = "digest"
    TOUR_ANNOUNCEMENT = "tour_announcement"
    LOW_SIGNAL = "low_signal"
    UNKNOWN = "unknown"


class LineKind(StrEnum):
    DATE = "date"
    TIME = "time"
    CITY = "city"
    VENUE = "venue"
    PRICE = "price"
    LINK = "link"
    CHAT = "chat"
    PROMO = "promo"
    TEXT = "text"
    SEPARATOR = "separator"
    UNKNOWN = "unknown"
    
