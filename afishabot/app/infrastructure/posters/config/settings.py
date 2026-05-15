from __future__ import annotations

from dataclasses import dataclass
from datetime import date


def _current_year() -> int:
    return date.today().year


@dataclass(slots=True)
class PosterExtractionSettings:
    default_year: int = _current_year()

    enable_relative_dates: bool = True
    enable_weekday_parsing: bool = True
    enable_date_ranges: bool = True
    enable_recurring_dates: bool = True

    max_dates_per_post: int = 20

    debug: bool = False


DEFAULT_POSTER_EXTRACTION_SETTINGS = PosterExtractionSettings()

