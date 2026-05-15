from enum import StrEnum


class EventLifecycleStatus(StrEnum):
    ANNOUNCED = "ANNOUNCED"
    UPDATED = "UPDATED"
    SOLD_OUT = "SOLD_OUT"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"
    PASSED = "PASSED"
    
