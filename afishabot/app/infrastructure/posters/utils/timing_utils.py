from __future__ import annotations

from datetime import time

from app.domain.posters.entities.poster_draft import PosterTiming
from app.infrastructure.posters.patterns.time_patterns import (
    DOORS_LABEL_RE,
    START_LABEL_RE,
    TIME_RANGE_RE,
    TIME_RE,
)


def detect_label(text: str | None) -> str | None:
    if not text:
        return None

    if DOORS_LABEL_RE.search(text):
        return "doors"

    if START_LABEL_RE.search(text):
        return "start"

    return None


def extract_timings(text: str | None) -> list[PosterTiming]:
    if not text:
        return []

    timings: list[PosterTiming] = []
    seen: set[tuple[str | None, time, str]] = set()

    for range_match in TIME_RANGE_RE.finditer(text):
        start_hour = int(range_match.group("start_hour"))
        start_minute = int(range_match.group("start_minute"))
        end_hour = int(range_match.group("end_hour"))
        end_minute = int(range_match.group("end_minute"))

        if (
            start_hour > 23
            or start_minute > 59
            or end_hour > 23
            or end_minute > 59
        ):
            continue

        start_time = time(hour=start_hour, minute=start_minute)
        end_time = time(hour=end_hour, minute=end_minute)

        context_start = max(range_match.start() - 40, 0)
        context_end = min(range_match.end() + 40, len(text))
        context_line = text[context_start:context_end].strip()

        start_label = detect_label(context_line)
        start_key = (start_label, start_time, f"{start_hour:02d}:{start_minute:02d}")
        if start_key not in seen:
            seen.add(start_key)
            timings.append(
                PosterTiming(
                    label=start_label,
                    time=start_time,
                    raw_time_text=f"{start_hour:02d}:{start_minute:02d}",
                    raw_label_text=context_line,
                )
            )

        end_label = None
        end_key = (end_label, end_time, f"{end_hour:02d}:{end_minute:02d}")
        if end_key not in seen:
            seen.add(end_key)
            timings.append(
                PosterTiming(
                    label=end_label,
                    time=end_time,
                    raw_time_text=f"{end_hour:02d}:{end_minute:02d}",
                    raw_label_text=context_line,
                )
            )

    for match in TIME_RE.finditer(text):
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))

        if hour > 23 or minute > 59:
            continue

        parsed_time = time(hour=hour, minute=minute)

        context_start = max(match.start() - 40, 0)
        context_end = min(match.end() + 40, len(text))
        context_line = text[context_start:context_end].strip()

        label = detect_label(context_line)
        raw_time_text = match.group(0)
        key = (label, parsed_time, raw_time_text)

        if key in seen:
            continue

        seen.add(key)
        timings.append(
            PosterTiming(
                label=label,
                time=parsed_time,
                raw_time_text=raw_time_text,
                raw_label_text=context_line,
            )
        )

    return timings

