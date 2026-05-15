from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class PostButtonInput:
    text: str = ""
    url: str | None = None 


@dataclass(slots=True)
class PostImageInput:
    telegram_file_id: str | None = None 
    telegram_file_unique_id: str | None = None 
    width: int | None = None 
    height: int | None = None
    file_size: int | None = None
    position: int | None = None


@dataclass(slots=True)
class PosterInput:
    title: str = ""
    text: str | None = None 
    html_text: str | None = None 
    buttons: list[PostButtonInput] = field(default_factory=list)
    images: list[PostImageInput] = field(default_factory=list)
    
    channel_id: int | None = None
    post_id: int | None = None
    
    published_at: datetime | None = None
    
