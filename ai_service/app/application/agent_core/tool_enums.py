from enum import StrEnum


class AgentToolCategory(StrEnum):
    EXTRACTION = "extraction"
    SEARCH = "search"
    VERIFICATION = "verification"
    ENTITY_RESOLUTION = "entity_resolution"
    MEDIA = "media"
    DATABASE = "database"
    UTILITY = "utility"


class AgentToolTrustLevel(StrEnum):
    LOW = "low"
    CANDIDATE = "candidate"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class AgentToolCostLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    

