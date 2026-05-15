from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any


class PosterAgentDraftStatus(str, Enum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    READY_TO_PUBLISH = "ready_to_publish"
    BLOCKED = "blocked"


class PosterAgentIssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PosterAgentLinkType(str, Enum):
    TICKET = "ticket"
    OFFICIAL = "official"
    SOURCE = "source"
    SOCIAL = "social"
    OTHER = "other"


@dataclass(slots=True)
class PosterAgentLink:
    url: str
    link_type: PosterAgentLinkType = PosterAgentLinkType.OTHER
    title: str | None = None
    verified: bool = False
    source: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class PosterAgentOccurrence:
    city: str | None = None
    date: str | None = None
    time: str | None = None
    venue: str | None = None
    address: str | None = None
    ticket_links: list[PosterAgentLink] = dataclass_field(default_factory=list)
    confidence: str | None = None
    verified: bool = False
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class PosterAgentValidationIssue:
    severity: PosterAgentIssueSeverity
    message: str
    field: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class PosterAgentDraft:
    title: str | None = None
    event_type: str | None = None
    artists: list[str] = dataclass_field(default_factory=list)
    description: str | None = None
    age_limit: int | None = None
    occurrences: list[PosterAgentOccurrence] = dataclass_field(default_factory=list)
    links: list[PosterAgentLink] = dataclass_field(default_factory=list)
    source_text: str | None = None
    status: PosterAgentDraftStatus = PosterAgentDraftStatus.DRAFT
    validation_issues: list[PosterAgentValidationIssue] = dataclass_field(default_factory=list)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def has_critical_issues(self) -> bool:
        return any(
            issue.severity == PosterAgentIssueSeverity.CRITICAL
            for issue in self.validation_issues
        )

    def has_errors(self) -> bool:
        return any(
            issue.severity in {
                PosterAgentIssueSeverity.ERROR,
                PosterAgentIssueSeverity.CRITICAL,
            }
            for issue in self.validation_issues
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "event_type": self.event_type,
            "artists": self.artists,
            "description": self.description,
            "age_limit": self.age_limit,
            "occurrences": [
                {
                    "city": occurrence.city,
                    "date": occurrence.date,
                    "time": occurrence.time,
                    "venue": occurrence.venue,
                    "address": occurrence.address,
                    "ticket_links": [
                        self._link_to_dict(link)
                        for link in occurrence.ticket_links
                    ],
                    "confidence": occurrence.confidence,
                    "verified": occurrence.verified,
                    "metadata": occurrence.metadata,
                }
                for occurrence in self.occurrences
            ],
            "links": [
                self._link_to_dict(link)
                for link in self.links
            ],
            "source_text": self.source_text,
            "status": self.status.value,
            "validation_issues": [
                {
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "field": issue.field,
                    "metadata": issue.metadata,
                }
                for issue in self.validation_issues
            ],
            "metadata": self.metadata,
        }

    def _link_to_dict(self, link) -> dict:
        if isinstance(link, str):
            return {
                "url": link,
                "link_type": "ticket",
                "title": None,
                "verified": False,
                "source": "unknown",
                "metadata": {},
            }

        if isinstance(link, dict):
            return {
                "url": link.get("url"),
                "link_type": self._value_to_string(link.get("link_type") or link.get("kind")),
                "title": link.get("title"),
                "verified": bool(link.get("verified")),
                "source": self._value_to_string(link.get("source") or link.get("source_type")),
                "metadata": link.get("metadata") or {},
            }

        return {
            "url": getattr(link, "url", None),
            "link_type": self._value_to_string(getattr(link, "link_type", None)),
            "title": getattr(link, "title", None),
            "verified": bool(getattr(link, "verified", False)),
            "source": self._value_to_string(getattr(link, "source", None)),
            "metadata": getattr(link, "metadata", None) or {},
        }

    def _value_to_string(self, value) -> str | None:
        if value is None:
            return None

        enum_value = getattr(value, "value", None)
        if enum_value is not None:
            return str(enum_value)

        return str(value)


@dataclass(slots=True)
class PosterAgentPublishDecision:
    can_publish: bool
    status: PosterAgentDraftStatus
    reason: str
    issues: list[PosterAgentValidationIssue] = dataclass_field(default_factory=list)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_publish": self.can_publish,
            "status": self.status.value,
            "reason": self.reason,
            "issues": [
                {
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "field": issue.field,
                    "metadata": issue.metadata,
                }
                for issue in self.issues
            ],
            "metadata": self.metadata,
        }
        

