from enum import StrEnum


class DateSource(StrEnum):
    EXPLICIT = "explicit"
    RANGE = "range"
    RELATIVE = "relative"
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    INFERRED = "inferred"
    
