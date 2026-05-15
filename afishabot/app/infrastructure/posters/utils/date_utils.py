from __future__ import annotations

import re
from datetime import date, timedelta

from app.infrastructure.posters.patterns.date_patterns import (
    DOTTED_DATE_RANGE_CROSS_MONTH_RE,
    DOTTED_DATE_RANGE_SAME_MONTH_RE,
    DOTTED_DATE_RE,
    MULTI_DOTTED_DATE_RE,
    MULTI_RU_DATE_RE,
    NEXT_WEEKDAY_RE,
    NEXT_WEEKEND_RE,
    RECURRING_DAILY_RE,
    RECURRING_WEEKLY_RE,
    RELATIVE_DATES,
    RELATIVE_DAYS_AGO_RE,
    RELATIVE_HOURS_AGO_RE,
    RELATIVE_IN_DAYS_RE,
    RELATIVE_IN_HOURS_RE,
    RELATIVE_IN_WEEKS_RE,
    RELATIVE_WEEKS_AGO_RE,
    RU_DATE_RANGE_CROSS_MONTH_RE,
    RU_DATE_RANGE_SAME_MONTH_RE,
    RU_DATE_RE,
    RU_MONTHS,
    RU_MULTI_DAY_SINGLE_MONTH_RE,
    RU_PART_OF_MONTH_RE,
    THIS_WEEKDAY_RE,
    THIS_WEEKEND_RE,
    WEEKDAY_INDEX_BY_KEYWORD,
    WEEKDAY_RANGE_RE,
    FROM_TO_RU_DATE_RANGE_RE,
    FROM_TO_DOTTED_DATE_RANGE_RE,
    RELATIVE_DAY_RANGE_RE,
    THIS_WEEK_RE,
    NEXT_WEEK_RE,
)

from app.infrastructure.posters.config.settings import (
    DEFAULT_POSTER_EXTRACTION_SETTINGS,
)

from app.infrastructure.posters.models import DateResult
from app.domain.posters.enums import DateSource


def extract_first_date(
    text: str | None,
    default_year: int | None = None,
    reference_date: date | None = None,
) -> tuple[date | None, str | None]:
    date_result = extract_date_range(
        text=text,
        default_year=default_year,
        reference_date=reference_date,
    )
    if date_result is None:
        return None, None

    return date_result.start_date, date_result.raw_text

def extract_date_range(
    text: str | None,
    default_year: int | None = None,
    reference_date: date | None = None,
) -> DateResult | None:
    if not text:
        return None

    reference = reference_date or date.today()

    relative_single = _extract_relative_single_date(
        text=text,
        reference_date=reference,
    )
    if relative_single is not None:
        resolved_date, raw_text = relative_single
        return DateResult(
            start_date=resolved_date,
            end_date=resolved_date,
            raw_text=raw_text,
            source=DateSource.RELATIVE,
        )

    relative_offset = _extract_relative_offset_date(
        text=text,
        reference_date=reference,
    )
    if relative_offset is not None:
        resolved_date, raw_text = relative_offset
        return DateResult(
            start_date=resolved_date,
            end_date=resolved_date,
            raw_text=raw_text,
            source=DateSource.RELATIVE,
        )

    relative_range = _extract_relative_day_range(
        text=text,
        reference_date=reference,
    )
    if relative_range is not None:
        start_date, end_date, raw_text = relative_range
        return DateResult(
            start_date=start_date,
            end_date=end_date,
            raw_text=raw_text,
            source=DateSource.RANGE,
        )

    weekday_range = _extract_weekday_range(
        text=text,
        reference_date=reference,
    )
    if weekday_range is not None:
        start_date, end_date, raw_text = weekday_range
        return DateResult(
            start_date=start_date,
            end_date=end_date,
            raw_text=raw_text,
            source=DateSource.WEEKDAY,
        )

    weekday_single = _extract_weekday_single_date(
        text=text,
        reference_date=reference,
    )
    if weekday_single is not None:
        resolved_date, raw_text = weekday_single
        return DateResult(
            start_date=resolved_date,
            end_date=resolved_date,
            raw_text=raw_text,
            source=DateSource.WEEKDAY,
        )

    weekend_range = _extract_weekend_range(
        text=text,
        reference_date=reference,
    )
    if weekend_range is not None:
        start_date, end_date, raw_text = weekend_range
        return DateResult(
            start_date=start_date,
            end_date=end_date,
            raw_text=raw_text,
            source=DateSource.WEEKEND,
        )

    week_range = _extract_week_range(
        text=text,
        reference_date=reference,
    )
    if week_range is not None:
        start_date, end_date, raw_text = week_range
        return DateResult(
            start_date=start_date,
            end_date=end_date,
            raw_text=raw_text,
            source=DateSource.RANGE,
        )

    part_of_month_range = _extract_part_of_month_range(
        text=text,
        default_year=default_year,
        reference_date=reference,
    )
    if part_of_month_range is not None:
        start_date, end_date, raw_text = part_of_month_range
        return DateResult(
            start_date=start_date,
            end_date=end_date,
            raw_text=raw_text,
            source=DateSource.RANGE,
        )

    explicit_range = _extract_explicit_range(
        text=text,
        default_year=default_year,
        reference_date=reference,
    )
    if explicit_range is not None:
        start_date, end_date, raw_text = explicit_range
        return DateResult(
            start_date=start_date,
            end_date=end_date,
            raw_text=raw_text,
            source=DateSource.RANGE,
        )

    explicit_single = _extract_explicit_single_date(
        text=text,
        default_year=default_year,
        reference_date=reference,
    )
    if explicit_single is not None:
        resolved_date, raw_text = explicit_single
        return DateResult(
            start_date=resolved_date,
            end_date=resolved_date,
            raw_text=raw_text,
            source=DateSource.EXPLICIT,
        )

    return None

def extract_all_dates(
    text: str | None,
    default_year: int | None = None,
    reference_date: date | None = None,
) -> list[tuple[date, str]]:
    if not text:
        return []

    reference = reference_date or date.today()
    result: list[tuple[date, str]] = []
    seen: set[date] = set()

    date_result = extract_date_range(
        text=text,
        default_year=default_year,
        reference_date=reference,
    )
    if date_result is not None:
        _add_date(result, seen, date_result.start_date, date_result.raw_text)
        if date_result.end_date != date_result.start_date:
            _add_date(result, seen, date_result.end_date, date_result.raw_text)

    for match in MULTI_DOTTED_DATE_RE.finditer(text):
        parsed = _build_dotted_date_from_match(
            match=match,
            default_year=default_year,
            reference_date=reference,
        )
        if parsed is not None:
            parsed_date, raw_text = parsed
            _add_date(result, seen, parsed_date, raw_text)

    for match in MULTI_RU_DATE_RE.finditer(text):
        parsed = _build_ru_date_from_match(
            match=match,
            default_year=default_year,
            reference_date=reference,
        )
        if parsed is not None:
            parsed_date, raw_text = parsed
            _add_date(result, seen, parsed_date, raw_text)

    single_month_multi = _extract_multi_day_single_month(
        text=text,
        default_year=default_year,
        reference_date=reference,
    )
    for parsed_date, raw_text in single_month_multi:
        _add_date(result, seen, parsed_date, raw_text)

    result.sort(key=lambda item: item[0])
    return result

def extract_recurring_weekday(
    text: str | None,
) -> int | None:
    if not text:
        return None

    match = RECURRING_WEEKLY_RE.search(text)
    if not match:
        return None

    raw = match.group("weekday") or match.group("weekday_alt")
    if not raw:
        return None

    normalized = raw.casefold()
    normalized = normalized.removesuffix("ам")
    normalized = normalized.removesuffix("ям")

    return _resolve_weekday_index(normalized)


def is_recurring_daily(text: str | None) -> bool:
    if not text:
        return False

    return bool(RECURRING_DAILY_RE.search(text))


def _extract_relative_single_date(
    text: str,
    reference_date: date,
) -> tuple[date, str] | None:
    lowered = text.casefold()

    for keyword, offset in RELATIVE_DATES:
        if keyword in lowered:
            return reference_date + timedelta(days=offset), keyword

    return None


def _extract_relative_offset_date(
    text: str,
    reference_date: date,
) -> tuple[date, str] | None:
    in_days_match = RELATIVE_IN_DAYS_RE.search(text)
    if in_days_match:
        days = int(in_days_match.group("value"))
        return reference_date + timedelta(days=days), in_days_match.group(0)

    ago_days_match = RELATIVE_DAYS_AGO_RE.search(text)
    if ago_days_match:
        days = int(ago_days_match.group("value"))
        return reference_date - timedelta(days=days), ago_days_match.group(0)

    in_hours_match = RELATIVE_IN_HOURS_RE.search(text)
    if in_hours_match:
        hours = int(in_hours_match.group("value"))
        day_offset = hours // 24
        return reference_date + timedelta(days=day_offset), in_hours_match.group(0)

    ago_hours_match = RELATIVE_HOURS_AGO_RE.search(text)
    if ago_hours_match:
        hours = int(ago_hours_match.group("value"))
        day_offset = hours // 24
        return reference_date - timedelta(days=day_offset), ago_hours_match.group(0)

    in_weeks_match = RELATIVE_IN_WEEKS_RE.search(text)
    if in_weeks_match:
        weeks = int(in_weeks_match.group("value"))
        return reference_date + timedelta(days=weeks * 7), in_weeks_match.group(0)

    ago_weeks_match = RELATIVE_WEEKS_AGO_RE.search(text)
    if ago_weeks_match:
        weeks = int(ago_weeks_match.group("value"))
        return reference_date - timedelta(days=weeks * 7), ago_weeks_match.group(0)

    return None


def _extract_weekday_single_date(
    text: str,
    reference_date: date,
) -> tuple[date, str] | None:
    next_match = NEXT_WEEKDAY_RE.search(text)
    if next_match:
        raw_weekday = next_match.group("weekday")
        weekday_index = _resolve_weekday_index(raw_weekday)
        if weekday_index is not None:
            resolved = _next_weekday(reference_date, weekday_index)
            return resolved, next_match.group(0)

    this_match = THIS_WEEKDAY_RE.search(text)
    if this_match:
        raw_weekday = this_match.group("weekday")
        weekday_index = _resolve_weekday_index(raw_weekday)
        if weekday_index is not None:
            resolved = _this_or_next_weekday_in_current_week(reference_date, weekday_index)
            return resolved, this_match.group(0)

    return None


def _extract_weekday_range(
    text: str,
    reference_date: date,
) -> tuple[date, date, str] | None:
    match = WEEKDAY_RANGE_RE.search(text)
    if not match:
        return None

    start_raw = match.group("start")
    end_raw = match.group("end")

    start_idx = _resolve_weekday_index(start_raw)
    end_idx = _resolve_weekday_index(end_raw)

    if start_idx is None or end_idx is None:
        return None

    start_date = _this_or_next_weekday_in_current_week(
        reference_date,
        start_idx,
    )

    end_date = _this_or_next_weekday_in_current_week(
        start_date,
        end_idx,
    )

    if end_date < start_date:
        end_date += timedelta(days=7)

    return start_date, end_date, match.group(0)



def _extract_weekend_range(
    text: str,
    reference_date: date,
) -> tuple[date, date, str] | None:
    next_match = NEXT_WEEKEND_RE.search(text)
    if next_match:
        saturday = _next_weekday(reference_date, 5)
        sunday = saturday + timedelta(days=1)
        return saturday, sunday, next_match.group(0)

    this_match = THIS_WEEKEND_RE.search(text)
    if this_match:
        saturday = _this_or_next_weekday_in_current_week(reference_date, 5)
        sunday = saturday + timedelta(days=1)
        return saturday, sunday, this_match.group(0)

    return None

def _extract_part_of_month_range(
    text: str,
    default_year: int | None,
    reference_date: date,
) -> tuple[date, date, str] | None:
    match = RU_PART_OF_MONTH_RE.search(text)
    if not match:
        return None

    part = match.group("part").casefold()
    month_name = match.group("month").casefold()
    month = RU_MONTHS.get(month_name)
    if month is None:
        return None

    year = _resolve_year(
        year_str=match.group("year"),
        default_year=default_year,
        reference_date=reference_date,
    )

    if part == "в начале":
        start_day, end_day = 1, 10
    elif part == "в середине":
        start_day, end_day = 11, 20
    else:
        start_day, end_day = 21, _days_in_month(year, month)

    try:
        return (
            date(year, month, start_day),
            date(year, month, end_day),
            match.group(0),
        )
    except ValueError:
        return None

def _extract_explicit_range(
    text: str,
    default_year: int | None,
    reference_date: date,
) -> tuple[date, date, str] | None:
    from_to_ru_match = FROM_TO_RU_DATE_RANGE_RE.search(text)
    if from_to_ru_match:
        start_day = int(from_to_ru_match.group("start_day"))
        end_day = int(from_to_ru_match.group("end_day"))

        month_name = from_to_ru_match.group("month").lower()
        month = RU_MONTHS.get(month_name)
        if month is None:
            return None

        explicit_year = bool(from_to_ru_match.group("year"))
        year = _resolve_year(
            year_str=from_to_ru_match.group("year"),
            default_year=default_year,
            reference_date=reference_date,
        )

        try:
            start_date = date(year, month, start_day)
            end_date = date(year, month, end_day)
        except ValueError:
            return None

        start_date = _adjust_future_date_if_needed(
            parsed_date=start_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )
        end_date = _adjust_future_date_if_needed(
            parsed_date=end_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        if end_date < start_date:
            return None

        return start_date, end_date, from_to_ru_match.group(0)

    from_to_dotted_match = FROM_TO_DOTTED_DATE_RANGE_RE.search(text)
    if from_to_dotted_match:
        start_day = int(from_to_dotted_match.group("start_day"))
        end_day = int(from_to_dotted_match.group("end_day"))
        month = int(from_to_dotted_match.group("month"))

        explicit_year = bool(from_to_dotted_match.group("year"))
        year = _resolve_year(
            year_str=from_to_dotted_match.group("year"),
            default_year=default_year,
            reference_date=reference_date,
        )

        try:
            start_date = date(year, month, start_day)
            end_date = date(year, month, end_day)
        except ValueError:
            return None

        start_date = _adjust_future_date_if_needed(
            parsed_date=start_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )
        end_date = _adjust_future_date_if_needed(
            parsed_date=end_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        if end_date < start_date:
            return None

        return start_date, end_date, from_to_dotted_match.group(0)

    ru_cross_match = RU_DATE_RANGE_CROSS_MONTH_RE.search(text)
    if ru_cross_match:
        start_day = int(ru_cross_match.group("start_day"))
        end_day = int(ru_cross_match.group("end_day"))
        start_month = RU_MONTHS.get(ru_cross_match.group("start_month").lower())
        end_month = RU_MONTHS.get(ru_cross_match.group("end_month").lower())

        if start_month is None or end_month is None:
            return None

        explicit_year = bool(ru_cross_match.group("year"))
        base_year = _resolve_year(
            year_str=ru_cross_match.group("year"),
            default_year=default_year,
            reference_date=reference_date,
        )

        start_year = base_year
        end_year = base_year

        if end_month < start_month:
            end_year += 1

        try:
            start_date = date(start_year, start_month, start_day)
            end_date = date(end_year, end_month, end_day)
        except ValueError:
            return None

        start_date = _adjust_future_date_if_needed(
            parsed_date=start_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )
        end_date = _adjust_future_date_if_needed(
            parsed_date=end_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        if end_date < start_date:
            return None

        return start_date, end_date, ru_cross_match.group(0)

    ru_same_match = RU_DATE_RANGE_SAME_MONTH_RE.search(text)
    if ru_same_match:
        start_day = int(ru_same_match.group("start_day"))
        end_day = int(ru_same_match.group("end_day"))
        month_name = ru_same_match.group("month").lower()
        month = RU_MONTHS.get(month_name)
        if month is None:
            return None

        explicit_year = bool(ru_same_match.group("year"))
        year = _resolve_year(
            year_str=ru_same_match.group("year"),
            default_year=default_year,
            reference_date=reference_date,
        )

        try:
            start_date = date(year, month, start_day)
            end_date = date(year, month, end_day)
        except ValueError:
            return None

        start_date = _adjust_future_date_if_needed(
            parsed_date=start_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )
        end_date = _adjust_future_date_if_needed(
            parsed_date=end_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        if end_date < start_date:
            return None

        return start_date, end_date, ru_same_match.group(0)

    dotted_cross_match = DOTTED_DATE_RANGE_CROSS_MONTH_RE.search(text)
    if dotted_cross_match:
        start_day = int(dotted_cross_match.group("start_day"))
        start_month = int(dotted_cross_match.group("start_month"))
        end_day = int(dotted_cross_match.group("end_day"))
        end_month = int(dotted_cross_match.group("end_month"))

        explicit_year = bool(
            dotted_cross_match.group("start_year")
            or dotted_cross_match.group("end_year")
        )

        start_year = _resolve_year(
            year_str=dotted_cross_match.group("start_year"),
            default_year=default_year,
            reference_date=reference_date,
        )

        end_year = (
            _resolve_year(
                year_str=dotted_cross_match.group("end_year"),
                default_year=default_year,
                reference_date=reference_date,
            )
            if dotted_cross_match.group("end_year")
            else start_year
        )

        if not dotted_cross_match.group("end_year") and end_month < start_month:
            end_year += 1

        try:
            start_date = date(start_year, start_month, start_day)
            end_date = date(end_year, end_month, end_day)
        except ValueError:
            return None

        start_date = _adjust_future_date_if_needed(
            parsed_date=start_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )
        end_date = _adjust_future_date_if_needed(
            parsed_date=end_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        if end_date < start_date:
            return None

        return start_date, end_date, dotted_cross_match.group(0)

    dotted_same_match = DOTTED_DATE_RANGE_SAME_MONTH_RE.search(text)
    if dotted_same_match:
        start_day = int(dotted_same_match.group("start_day"))
        end_day = int(dotted_same_match.group("end_day"))
        month = int(dotted_same_match.group("month"))

        explicit_year = bool(dotted_same_match.group("year"))
        year = _resolve_year(
            year_str=dotted_same_match.group("year"),
            default_year=default_year,
            reference_date=reference_date,
        )

        try:
            start_date = date(year, month, start_day)
            end_date = date(year, month, end_day)
        except ValueError:
            return None

        start_date = _adjust_future_date_if_needed(
            parsed_date=start_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )
        end_date = _adjust_future_date_if_needed(
            parsed_date=end_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        if end_date < start_date:
            return None

        return start_date, end_date, dotted_same_match.group(0)

    return None

def _extract_explicit_single_date(
    text: str,
    default_year: int | None,
    reference_date: date,
) -> tuple[date, str] | None:
    dotted_match = DOTTED_DATE_RE.search(text)
    if dotted_match:
        day = int(dotted_match.group("day"))
        month = int(dotted_match.group("month"))
        explicit_year = bool(dotted_match.group("year"))
        year = _resolve_year(
            year_str=dotted_match.group("year"),
            default_year=default_year,
            reference_date=reference_date,
        )

        try:
            parsed_date = date(year, month, day)
        except ValueError:
            return None

        parsed_date = _adjust_future_date_if_needed(
            parsed_date=parsed_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        return parsed_date, dotted_match.group(0)

    ru_match = RU_DATE_RE.search(text)
    if ru_match:
        day = int(ru_match.group("day"))
        month_name = ru_match.group("month").lower()
        month = RU_MONTHS.get(month_name)
        if month is None:
            return None

        explicit_year = bool(ru_match.group("year"))
        year = _resolve_year(
            year_str=ru_match.group("year"),
            default_year=default_year,
            reference_date=reference_date,
        )

        try:
            parsed_date = date(year, month, day)
        except ValueError:
            return None

        parsed_date = _adjust_future_date_if_needed(
            parsed_date=parsed_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        return parsed_date, ru_match.group(0)

    return None


def _extract_multi_day_single_month(
    text: str,
    default_year: int | None,
    reference_date: date,
) -> list[tuple[date, str]]:
    match = RU_MULTI_DAY_SINGLE_MONTH_RE.search(text)
    if not match:
        return []

    month_name = match.group("month").lower()
    month = RU_MONTHS.get(month_name)
    if month is None:
        return []

    explicit_year = bool(match.group("year"))

    year = _resolve_year(
        year_str=match.group("year"),
        default_year=default_year,
        reference_date=reference_date,
    )

    days_text = match.group("days")
    raw_days = re.split(r"\s*,\s*|\s*/\s*|\s+и\s+", days_text)

    result: list[tuple[date, str]] = []

    for raw_day in raw_days:
        raw_day = raw_day.strip()

        if not raw_day.isdigit():
            continue

        day = int(raw_day)

        try:
            parsed_date = date(year, month, day)
        except ValueError:
            continue

        parsed_date = _adjust_future_date_if_needed(
            parsed_date=parsed_date,
            reference_date=reference_date,
            explicit_year=explicit_year,
        )

        result.append(
            (
                parsed_date,
                f"{raw_day} {month_name}",
            )
        )

    return result

def _extract_relative_day_range(
    text: str,
    reference_date: date,
) -> tuple[date, date, str] | None:
    match = RELATIVE_DAY_RANGE_RE.search(text)
    if not match:
        return None

    start_keyword = match.group("start").casefold()
    end_keyword = match.group("end").casefold()

    offset_map = {
        "сегодня": 0,
        "завтра": 1,
        "послезавтра": 2,
    }

    start_offset = offset_map.get(start_keyword)
    end_offset = offset_map.get(end_keyword)

    if start_offset is None or end_offset is None:
        return None

    start_date = reference_date + timedelta(days=start_offset)
    end_date = reference_date + timedelta(days=end_offset)

    if end_date < start_date:
        return None

    return start_date, end_date, match.group(0)

def _extract_week_range(
    text: str,
    reference_date: date,
) -> tuple[date, date, str] | None:
    next_match = NEXT_WEEK_RE.search(text)
    if next_match:
        start_of_current_week = reference_date - timedelta(days=reference_date.weekday())
        start_date = start_of_current_week + timedelta(days=7)
        end_date = start_date + timedelta(days=6)
        return start_date, end_date, next_match.group(0)

    this_match = THIS_WEEK_RE.search(text)
    if this_match:
        start_date = reference_date - timedelta(days=reference_date.weekday())
        end_date = start_date + timedelta(days=6)
        return start_date, end_date, this_match.group(0)

    return None

def _build_dotted_date_from_match(
    match: re.Match[str],
    default_year: int | None,
    reference_date: date,
) -> tuple[date, str] | None:
    day = int(match.group("day"))
    month = int(match.group("month"))
    explicit_year = bool(match.group("year"))
    year = _resolve_year(
        year_str=match.group("year"),
        default_year=default_year,
        reference_date=reference_date,
    )

    try:
        parsed_date = date(year, month, day)
    except ValueError:
        return None

    parsed_date = _adjust_future_date_if_needed(
        parsed_date=parsed_date,
        reference_date=reference_date,
        explicit_year=explicit_year,
    )

    return parsed_date, match.group(0)


def _build_ru_date_from_match(
    match: re.Match[str],
    default_year: int | None,
    reference_date: date,
) -> tuple[date, str] | None:
    day = int(match.group("day"))
    month_name = match.group("month").lower()
    month = RU_MONTHS.get(month_name)
    if month is None:
        return None

    explicit_year = bool(match.group("year"))
    year = _resolve_year(
        year_str=match.group("year"),
        default_year=default_year,
        reference_date=reference_date,
    )

    try:
        parsed_date = date(year, month, day)
    except ValueError:
        return None

    parsed_date = _adjust_future_date_if_needed(
        parsed_date=parsed_date,
        reference_date=reference_date,
        explicit_year=explicit_year,
    )

    return parsed_date, match.group(0)


def _add_date(
    result: list[tuple[date, str]],
    seen: set[date],
    parsed_date: date,
    raw_text: str,
) -> None:
    if parsed_date in seen:
        return

    seen.add(parsed_date)
    result.append((parsed_date, raw_text))


def _adjust_future_date_if_needed(
    parsed_date: date,
    reference_date: date,
    explicit_year: bool,
) -> date:
    if explicit_year:
        return parsed_date

    if parsed_date >= reference_date:
        return parsed_date

    try:
        return date(
            parsed_date.year + 1,
            parsed_date.month,
            parsed_date.day,
        )
    except ValueError:
        return parsed_date
    

def _resolve_year(
    year_str: str | None,
    default_year: int | None,
    reference_date: date,
) -> int:
    if year_str:
        year = int(year_str)
        if year < 100:
            year += 2000
        return year

    if default_year is not None:
        return default_year

    settings_year = DEFAULT_POSTER_EXTRACTION_SETTINGS.default_year
    if settings_year is not None:
        return settings_year

    return reference_date.year


def _resolve_weekday_index(raw_weekday: str | None) -> int | None:
    if not raw_weekday:
        return None

    return WEEKDAY_INDEX_BY_KEYWORD.get(raw_weekday.casefold())


def _this_or_next_weekday_in_current_week(
    reference_date: date,
    target_weekday: int,
) -> date:
    current_weekday = reference_date.weekday()
    delta = target_weekday - current_weekday

    if delta < 0:
        delta += 7

    return reference_date + timedelta(days=delta)


def _next_weekday(
    reference_date: date,
    target_weekday: int,
) -> date:
    current_weekday = reference_date.weekday()
    delta = target_weekday - current_weekday

    if delta <= 0:
        delta += 7

    return reference_date + timedelta(days=delta)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    current_month = date(year, month, 1)
    return (next_month - current_month).days

