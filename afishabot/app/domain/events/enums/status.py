from enum import StrEnum

class EventStatus(StrEnum):
    DRAFT     = "draft"
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    POSTED    = "posted"
    UPDATED   = "updated"
    CANCELLED = "deleted"

