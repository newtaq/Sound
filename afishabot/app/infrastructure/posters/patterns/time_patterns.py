from __future__ import annotations

import re


TIME_RE = re.compile(
    r"""
    \b
    (?P<hour>\d{1,2})
    :
    (?P<minute>\d{2})
    \b
    """,
    re.VERBOSE,
)


TIME_RANGE_RE = re.compile(
    r"""
    \b
    (?P<start_hour>\d{1,2})
    :
    (?P<start_minute>\d{2})
    \s*
    (?:-|–|—|до)
    \s*
    (?P<end_hour>\d{1,2})
    :
    (?P<end_minute>\d{2})
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


DOORS_LABEL_RE = re.compile(
    r"""
    \b
    (?:двери|doors)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


START_LABEL_RE = re.compile(
    r"""
    \b
    (?:начало|start|show)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

