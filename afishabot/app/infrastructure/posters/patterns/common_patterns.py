from __future__ import annotations

import re


NUMBER_RE = re.compile(
    r"""
    \b
    \d+
    \b
    """,
    re.VERBOSE,
)


AGE_LIMIT_RE = re.compile(
    r"""
    \b
    (?P<age>\d{1,2})
    \s*
    (?:\+|лет)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


UPPER_TOKEN_RE = re.compile(
    r"""
    \b
    [A-ZА-ЯЁ]
    [A-ZА-ЯЁ0-9_-]{2,}
    \b
    """,
    re.VERBOSE,
)


CITY_TOKEN_RE = re.compile(
    r"""
    \b
    [A-ZА-ЯЁ]
    [A-Za-zА-Яа-яЁё\- ]{1,40}
    \b
    """,
    re.VERBOSE,
)


SEPARATOR_LINE_RE = re.compile(
    r"""
    ^
    [-–—=_•·]{3,}
    $
    """,
    re.VERBOSE,
)


WHITESPACE_RE = re.compile(
    r"""
    [ \t]+
    """,
    re.VERBOSE,
)


NEWLINE_RE = re.compile(
    r"""
    \r\n?
    """,
    re.VERBOSE,
)

