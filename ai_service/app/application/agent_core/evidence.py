from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any


class EvidenceConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"


@dataclass(slots=True)
class EvidenceSource:
    source_type: str
    title: str | None = None
    url: str | None = None
    raw_text: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class AgentEvidence:
    field: str
    value: Any
    confidence: EvidenceConfidence = EvidenceConfidence.LOW
    status: EvidenceStatus = EvidenceStatus.UNVERIFIED
    source: EvidenceSource | None = None
    explanation: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class AgentEvidenceSet:
    items: list[AgentEvidence] = dataclass_field(default_factory=list)

    def add(
        self,
        evidence: AgentEvidence,
    ) -> None:
        self.items.append(evidence)

    def verified_items(self) -> list[AgentEvidence]:
        return [
            item
            for item in self.items
            if item.status == EvidenceStatus.VERIFIED
        ]

    def unverified_items(self) -> list[AgentEvidence]:
        return [
            item
            for item in self.items
            if item.status == EvidenceStatus.UNVERIFIED
        ]

    def conflicted_items(self) -> list[AgentEvidence]:
        return [
            item
            for item in self.items
            if item.status == EvidenceStatus.CONFLICTED
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "field": item.field,
                    "value": item.value,
                    "confidence": item.confidence.value,
                    "status": item.status.value,
                    "source": (
                        {
                            "source_type": item.source.source_type,
                            "title": item.source.title,
                            "url": item.source.url,
                            "raw_text": item.source.raw_text,
                            "metadata": item.source.metadata,
                        }
                        if item.source is not None
                        else None
                    ),
                    "explanation": item.explanation,
                    "metadata": item.metadata,
                }
                for item in self.items
            ]
        }
        

