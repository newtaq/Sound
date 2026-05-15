from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

from ..enums import EventLifecycleStatus


@dataclass(slots=True)
class PosterLink:
    url: str
    label: str | None = None 
    link_type: str | None = None 
    
    
@dataclass(slots=True)
class PosterImageRef:
    telegram_file_id: str | None = None 
    telegram_file_unique_id: str | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    position: int | None = None
    

@dataclass(slots=True)
class PosterTiming:
    label: str | None = None
    time: time | None = None
    
    raw_time_text: str | None = None
    raw_label_text: str | None = None
    
    
    
@dataclass(slots=True)
class PosterOccurrenceDraft:
    city_name: str | None = None 
    venue_name: str | None = None
    address: str | None = None
    
    event_date: date | None = None
    timings: list[PosterTiming] = field(default_factory=list)
    
    raw_date_text: str | None = None
    raw_line: str | None = None
    


@dataclass(slots=True)
class PosterDraft:
    title: str | None = None
    description: str | None = None

    artist_names: list[str] = field(default_factory=list)
    organizer_names: list[str] = field(default_factory=list)

    occurrences: list[PosterOccurrenceDraft] = field(default_factory=list)

    age_limit: int | None = None
    promo_codes: list[str] = field(default_factory=list)
    ticket_links: list[PosterLink] = field(default_factory=list)

    lifecycle_status: EventLifecycleStatus = EventLifecycleStatus.ANNOUNCED

    source_channel_id: int | None = None
    source_post_id: int | None = None

    images: list[PosterImageRef] = field(default_factory=list)

    raw_text: str | None = None
    warnings: list[str] = field(default_factory=list)
    detected_conflicts: list[str] = field(default_factory=list)
    
