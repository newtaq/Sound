from __future__ import annotations

import re


RU_MONTHS: dict[str, int] = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

ENGLISH_MONTHS: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

RELATIVE_DATES: tuple[tuple[str, int], ...] = (
    ("позавчера", -2),
    ("вчера", -1),
    ("сегодня", 0),
    ("завтра", 1),
    ("послезавтра", 2),
)

WEEKDAY_INDEX_BY_KEYWORD: dict[str, int] = {
    "понедельник": 0,
    "понедельника": 0,
    "понедельнике": 0,
    "вторник": 1,
    "вторника": 1,
    "среда": 2,
    "среду": 2,
    "среды": 2,
    "четверг": 3,
    "четверга": 3,
    "пятница": 4,
    "пятницу": 4,
    "пятницы": 4,
    "суббота": 5,
    "субботу": 5,
    "субботы": 5,
    "воскресенье": 6,
    "воскресенья": 6,
    "пн": 0,
    "вт": 1,
    "ср": 2,
    "чт": 3,
    "пт": 4,
    "сб": 5,
    "вс": 6,
}


RU_DATE_RE = re.compile(
    r"""
    \b
    (?P<day>\d{1,2})
    \s+
    (?P<month>
        января|февраля|марта|апреля|мая|июня|
        июля|августа|сентября|октября|ноября|декабря
    )
    (?:\s+(?P<year>\d{2,4}))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

DOTTED_DATE_RE = re.compile(
    r"""
    \b
    (?P<day>\d{1,2})
    [./-]
    (?P<month>\d{1,2})
    (?:[./-](?P<year>\d{2,4}))?
    \b
    """,
    re.VERBOSE,
)

DOTTED_DATE_ANY_RE = re.compile(
    r"""
    (?P<day>\d{1,2})
    [./-]
    (?P<month>\d{1,2})
    (?:[./-](?P<year>\d{2,4}))?
    """,
    re.VERBOSE,
)

ENGLISH_DATE_RE = re.compile(
    r"""
    \b
    (?P<day>\d{1,2})
    \s+
    (?P<month>
        january|february|march|april|may|june|
        july|august|september|october|november|december
    )
    (?:\s+(?P<year>\d{4}))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RU_DATE_RANGE_SAME_MONTH_RE = re.compile(
    r"""
    \b
    (?P<start_day>\d{1,2})
    \s*[-–—]\s*
    (?P<end_day>\d{1,2})
    \s+
    (?P<month>
        января|февраля|марта|апреля|мая|июня|
        июля|августа|сентября|октября|ноября|декабря
    )
    (?:\s+(?P<year>\d{2,4}))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RU_DATE_RANGE_CROSS_MONTH_RE = re.compile(
    r"""
    \b
    (?P<start_day>\d{1,2})
    \s+
    (?P<start_month>
        января|февраля|марта|апреля|мая|июня|
        июля|августа|сентября|октября|ноября|декабря
    )
    \s*[-–—]\s*
    (?P<end_day>\d{1,2})
    \s+
    (?P<end_month>
        января|февраля|марта|апреля|мая|июня|
        июля|августа|сентября|октября|ноября|декабря
    )
    (?:\s+(?P<year>\d{2,4}))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

DOTTED_DATE_RANGE_SAME_MONTH_RE = re.compile(
    r"""
    \b
    (?P<start_day>\d{1,2})
    \s*[-–—]\s*
    (?P<end_day>\d{1,2})
    [./-]
    (?P<month>\d{1,2})
    (?:[./-](?P<year>\d{2,4}))?
    \b
    """,
    re.VERBOSE,
)

DOTTED_DATE_RANGE_CROSS_MONTH_RE = re.compile(
    r"""
    \b
    (?P<start_day>\d{1,2})
    [./-]
    (?P<start_month>\d{1,2})
    (?:[./-](?P<start_year>\d{2,4}))?
    \s*[-–—]\s*
    (?P<end_day>\d{1,2})
    [./-]
    (?P<end_month>\d{1,2})
    (?:[./-](?P<end_year>\d{2,4}))?
    \b
    """,
    re.VERBOSE,
)

MULTI_DOTTED_DATE_RE = re.compile(
    r"""
    \b
    (?P<day>\d{1,2})
    [./-]
    (?P<month>\d{1,2})
    (?:[./-](?P<year>\d{2,4}))?
    \b
    """,
    re.VERBOSE,
)

MULTI_RU_DATE_RE = re.compile(
    r"""
    \b
    (?P<day>\d{1,2})
    \s+
    (?P<month>
        января|февраля|марта|апреля|мая|июня|
        июля|августа|сентября|октября|ноября|декабря
    )
    (?:\s+(?P<year>\d{2,4}))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RU_MULTI_DAY_SINGLE_MONTH_RE = re.compile(
    r"""
    \b
    (?P<days>
        \d{1,2}
        (?:
            \s*,\s*\d{1,2}|
            \s*/\s*\d{1,2}|
            \s+и\s+\d{1,2}
        )+
    )
    \s+
    (?P<month>
        января|февраля|марта|апреля|мая|июня|
        июля|августа|сентября|октября|ноября|декабря
    )
    (?:\s+(?P<year>\d{2,4}))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

THIS_WEEKDAY_RE = re.compile(
    r"""
    \b
    (?:
        в\s+этот|
        в\s+эту|
        в
    )
    \s+
    (?P<weekday>
        понедельник(?:а|е)?|
        вторник(?:а)?|
        сред(?:а|у|ы)|
        четверг(?:а)?|
        пятниц(?:а|у|ы)|
        суббот(?:а|у|ы)|
        воскресень(?:е|я)
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

NEXT_WEEKDAY_RE = re.compile(
    r"""
    \b
    в
    \s+
    следующ(?:
        ий|ую|ее|ем|ей
    )
    \s+
    (?P<weekday>
        понедельник(?:а|е)?|
        вторник(?:а)?|
        сред(?:а|у|ы)|
        четверг(?:а)?|
        пятниц(?:а|у|ы)|
        суббот(?:а|у|ы)|
        воскресень(?:е|я)
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

THIS_WEEKEND_RE = re.compile(
    r"""
    \b
    (?:
        на|
        в
    )
    \s+
    (?:
        эти|
        этот
    )?
    \s*
    выходн(?:ые|ых)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

NEXT_WEEKEND_RE = re.compile(
    r"""
    \b
    (?:
        на|
        в
    )
    \s+
    следующ(?:
        ие|их|ий
    )
    \s+
    выходн(?:ые|ых)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

WEEKDAY_RANGE_RE = re.compile(
    r"""
    \b
    (?:
        с
        \s+
    )?
    (?P<start>
        понедельник(?:а|е)?|
        вторник(?:а)?|
        сред(?:а|у|ы)|
        четверг(?:а)?|
        пятниц(?:а|у|ы)|
        суббот(?:а|у|ы)|
        воскресень(?:е|я)|
        пн|вт|ср|чт|пт|сб|вс
    )
    \s*
    (?:-|–|—|по)
    \s*
    (?P<end>
        понедельник(?:а|е)?|
        вторник(?:а)?|
        сред(?:а|у|ы)|
        четверг(?:а)?|
        пятниц(?:а|у|ы)|
        суббот(?:а|у|ы)|
        воскресень(?:е|я)|
        пн|вт|ср|чт|пт|сб|вс
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RELATIVE_IN_DAYS_RE = re.compile(
    r"""
    \b
    (?:
        уже\s+через|
        через
    )
    \s+
    (?P<value>\d{1,3})
    \s+
    (?P<unit>день|дня|дней)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RELATIVE_DAYS_AGO_RE = re.compile(
    r"""
    \b
    (?P<value>\d{1,3})
    \s+
    (?P<unit>день|дня|дней)
    \s+
    назад
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RELATIVE_IN_HOURS_RE = re.compile(
    r"""
    \b
    (?:
        уже\s+через|
        через
    )
    \s+
    (?P<value>\d{1,3})
    \s+
    (?P<unit>час|часа|часов)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RELATIVE_HOURS_AGO_RE = re.compile(
    r"""
    \b
    (?P<value>\d{1,3})
    \s+
    (?P<unit>час|часа|часов)
    \s+
    назад
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RELATIVE_IN_WEEKS_RE = re.compile(
    r"""
    \b
    (?:
        уже\s+через|
        через
    )
    \s+
    (?P<value>\d{1,3})
    \s+
    (?P<unit>неделю|недели|недель)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RELATIVE_WEEKS_AGO_RE = re.compile(
    r"""
    \b
    (?P<value>\d{1,3})
    \s+
    (?P<unit>неделю|недели|недель)
    \s+
    назад
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RECURRING_DAILY_RE = re.compile(
    r"""
    \b
    (?:
        ежедневно|
        каждый\s+день
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RECURRING_WEEKLY_RE = re.compile(
    r"""
    \b
    (?:
        кажд(?:ый|ую|ое)\s+
        (?P<weekday>
            понедельник(?:а|е)?|
            вторник(?:а)?|
            сред(?:а|у|ы)|
            четверг(?:а)?|
            пятниц(?:а|у|ы)|
            суббот(?:а|у|ы)|
            воскресень(?:е|я)
        )|
        по\s+
        (?P<weekday_alt>
            понедельник(?:ам|ам)?|
            вторник(?:ам|ам)?|
            сред(?:ам|ам)?|
            четверг(?:ам|ам)?|
            пятниц(?:ам|ам)?|
            суббот(?:ам|ам)?|
            воскресень(?:ям|ям)
        )
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

RU_PART_OF_MONTH_RE = re.compile(
    r"""
    \b
    (?P<part>в\s+начале|в\s+середине|в\s+конце)
    \s+
    (?P<month>
        января|февраля|марта|апреля|мая|июня|
        июля|августа|сентября|октября|ноября|декабря
    )
    (?:\s+(?P<year>\d{2,4}))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

PIPE_OCCURRENCE_RE = re.compile(
    r"""
    ^
    (?P<date>\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)
    \s*\|\s*
    (?P<artist>[^|]{2,100}?)
    \s*\|\s*
    (?P<venue_city>[^|]{2,100}?)
    \s*\|\s*
    (?P<times>[^|]{2,40})
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)

MULTICITY_DATE_CITY_RE = re.compile(
    r"""
    ^
    (?P<date>\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)
    \s*[\-–—]\s*
    (?P<city>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё\- ]{1,50})
    $
    """,
    re.VERBOSE,
)

INLINE_CITY_DATE_RE = re.compile(
    r"""
    ^
    (?P<city>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё\- ]{1,50})
    \s*,\s*
    (?P<rest>.+)
    $
    """,
    re.VERBOSE,
)

FROM_TO_RU_DATE_RANGE_RE = re.compile(
    r"""
    с\s*
    (?P<start_day>\d{1,2})
    \s*
    по\s*
    (?P<end_day>\d{1,2})
    \s+
    (?P<month>
        января|
        февраля|
        марта|
        апреля|
        мая|
        июня|
        июля|
        августа|
        сентября|
        октября|
        ноября|
        декабря
    )
    (?:\s+(?P<year>\d{2,4}))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

FROM_TO_DOTTED_DATE_RANGE_RE = re.compile(
    r"""
    с\s*
    (?P<start_day>\d{1,2})
    \s*
    по\s*
    (?P<end_day>\d{1,2})
    \.
    (?P<month>\d{1,2})
    (?:\.
        (?P<year>\d{2,4})
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)

RELATIVE_DAY_RANGE_RE = re.compile(
    r"""
    (?P<start>
        сегодня|
        завтра|
        послезавтра
    )
    \s*
    (?:и|-|–)
    \s*
    (?P<end>
        сегодня|
        завтра|
        послезавтра
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

THIS_WEEK_RE = re.compile(
    r"""
    \b
    (?:
        на|
        в
    )
    \s+
    (?:
        этой|
        эту
    )?
    \s*
    недел(?:е|ю)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

NEXT_WEEK_RE = re.compile(
    r"""
    \b
    (?:
        на|
        в
    )
    \s+
    следующ(?:ей|ую)
    \s+
    недел(?:е|ю)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

