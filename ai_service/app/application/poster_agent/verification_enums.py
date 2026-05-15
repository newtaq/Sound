from enum import StrEnum


class PosterAgentVerificationRecommendation(StrEnum):
    AUTO_PUBLISH = "auto_publish"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class PosterAgentFactStatus(StrEnum):
    INPUT = "input"
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"


class PosterAgentSourceType(StrEnum):
    INPUT_TEXT = "input_text"
    OCR = "ocr"
    QR = "qr"
    URL = "url"
    SEARCH = "search"
    DATABASE = "database"
    MEDIA_SEARCH = "media_search"
    MANUAL = "manual"
    UNKNOWN = "unknown"
    

