from dataclasses import dataclass, field
from typing import Any

from app.application.poster_agent.verification_enums import (
    PosterAgentFactStatus,
    PosterAgentSourceType,
    PosterAgentVerificationRecommendation,
)

@dataclass(slots=True)
class PosterAgentVerificationFact:
    field: str
    value: Any
    status: PosterAgentFactStatus
    source_type: PosterAgentSourceType = PosterAgentSourceType.UNKNOWN
    confidence: float = 0.0
    source_url: str | None = None
    source_title: str | None = None
    explanation: str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "status": self.status.value,
            "source_type": self.source_type.value,
            "confidence": self.confidence,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "explanation": self.explanation,
        }


@dataclass(slots=True)
class PosterAgentVerificationOccurrence:
    city_name: str | None = None
    venue_name: str | None = None
    address: str | None = None
    event_date: str | None = None
    start_time: str | None = None
    doors_time: str | None = None
    confidence: float = 0.0
    verified: bool = False
    source_url: str | None = None
    explanation: str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "city_name": self.city_name,
            "venue_name": self.venue_name,
            "address": self.address,
            "event_date": self.event_date,
            "start_time": self.start_time,
            "doors_time": self.doors_time,
            "confidence": self.confidence,
            "verified": self.verified,
            "source_url": self.source_url,
            "explanation": self.explanation,
        }


@dataclass(slots=True)
class PosterAgentVerificationLink:
    url: str
    kind: str = "unknown"
    title: str | None = None
    verified: bool = False
    confidence: float = 0.0
    source_type: PosterAgentSourceType = PosterAgentSourceType.UNKNOWN
    explanation: str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "url": self.url,
            "kind": self.kind,
            "title": self.title,
            "verified": self.verified,
            "confidence": self.confidence,
            "source_type": self.source_type.value,
            "explanation": self.explanation,
        }


@dataclass(slots=True)
class PosterAgentVerificationResult:
    title: str | None = None
    event_type: str | None = None
    artists: list[str] = field(default_factory=list)
    organizers: list[str] = field(default_factory=list)
    age_limit: int | None = None
    description: str | None = None
    occurrences: list[PosterAgentVerificationOccurrence] = field(default_factory=list)
    links: list[PosterAgentVerificationLink] = field(default_factory=list)
    facts: list[PosterAgentVerificationFact] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    overall_confidence: float = 0.0
    recommendation: PosterAgentVerificationRecommendation = (
        PosterAgentVerificationRecommendation.NEEDS_REVIEW
    )
    explanation: str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "title": self.title,
            "event_type": self.event_type,
            "artists": list(self.artists),
            "organizers": list(self.organizers),
            "age_limit": self.age_limit,
            "description": self.description,
            "occurrences": [
                occurrence.to_dict()
                for occurrence in self.occurrences
            ],
            "links": [
                link.to_dict()
                for link in self.links
            ],
            "facts": [
                fact.to_dict()
                for fact in self.facts
            ],
            "missing_fields": list(self.missing_fields),
            "conflicts": list(self.conflicts),
            "warnings": list(self.warnings),
            "overall_confidence": self.overall_confidence,
            "recommendation": self.recommendation.value,
            "explanation": self.explanation,
        }
        

