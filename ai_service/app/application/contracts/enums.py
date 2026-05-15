from enum import StrEnum


class AIMode(StrEnum):
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
    AGENT = "agent"


class AIMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AIMediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class AIResponseStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class AIStreamEventType(StrEnum):
    STARTED = "started"
    MESSAGE_UPDATED = "message_updated"
    MESSAGE_FINISHED = "message_finished"
    FINISHED = "finished"
    ERROR = "error"


class AIContentType(StrEnum):
    EVENT_ANNOUNCEMENT = "event_announcement"
    TOUR_ANNOUNCEMENT = "tour_announcement"
    EVENT_UPDATE = "event_update"
    TOUR_UPDATE = "tour_update"
    EVENT_PROMO = "event_promo"
    EVENT_REMINDER = "event_reminder"
    EVENT_RECAP = "event_recap"
    EVENT_CANCELLED = "event_cancelled"
    EVENT_POSTPONED = "event_postponed"
    TICKET_UPDATE = "ticket_update"
    LINEUP_UPDATE = "lineup_update"
    VENUE_UPDATE = "venue_update"
    TRASH = "trash"
    UNKNOWN = "unknown"


class AIContentPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TRASH = "trash"


class AIDecisionType(StrEnum):
    CREATE_EVENT_CANDIDATE = "create_event_candidate"
    CREATE_TOUR_CANDIDATE = "create_tour_candidate"
    UPDATE_EVENT = "update_event"
    UPDATE_TOUR = "update_tour"
    ATTACH_PROMO = "attach_promo"
    ATTACH_REMINDER = "attach_reminder"
    ATTACH_RECAP_MEDIA = "attach_recap_media"
    MARK_EVENT_CANCELLED = "mark_event_cancelled"
    MARK_EVENT_POSTPONED = "mark_event_postponed"
    UPDATE_TICKETS = "update_tickets"
    UPDATE_LINEUP = "update_lineup"
    UPDATE_VENUE = "update_venue"
    IGNORE = "ignore"
    NEEDS_REVIEW = "needs_review"
    

