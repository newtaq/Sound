from __future__ import annotations

from app.infrastructure.posters.classifiers.classifier_types import MessageKind
from app.infrastructure.posters.models.message_classification import MessageClassification
from app.infrastructure.posters.patterns.message_kind_patterns import (
    DIGEST_MESSAGE_RE,
    EVENT_MESSAGE_RE,
    GIVEAWAY_MESSAGE_RE,
    LOW_SIGNAL_MESSAGE_RE,
    PROMO_MESSAGE_RE,
    TOUR_MESSAGE_RE,
)
from app.infrastructure.posters.semantics.message_kind_markers import (
    DIGEST_EXACT_VALUES,
    LOW_SIGNAL_EXACT_VALUES,
    PROMO_EXACT_VALUES,
)
from app.infrastructure.posters.utils.text_utils import split_lines


class MessageKindClassifier:
    def classify(self, text: str | None) -> MessageClassification:
        if not text:
            return MessageClassification(
                kind=MessageKind.UNKNOWN,
                confidence=0.0,
                reasons=["empty_text"],
            )

        normalized = text.strip()
        if not normalized:
            return MessageClassification(
                kind=MessageKind.UNKNOWN,
                confidence=0.0,
                reasons=["empty_text"],
            )

        lowered = normalized.casefold()
        lines = [line.strip() for line in split_lines(normalized) if line.strip()]
        reasons: list[str] = []

        if GIVEAWAY_MESSAGE_RE.search(lowered):
            reasons.append("giveaway_marker")
            return MessageClassification(
                kind=MessageKind.GIVEAWAY,
                confidence=0.95,
                reasons=reasons,
            )

        if lowered in PROMO_EXACT_VALUES or PROMO_MESSAGE_RE.search(lowered):
            reasons.append("promo_marker")
            return MessageClassification(
                kind=MessageKind.PROMO,
                confidence=0.9,
                reasons=reasons,
            )

        if lowered in DIGEST_EXACT_VALUES or DIGEST_MESSAGE_RE.search(lowered):
            reasons.append("digest_marker")
            return MessageClassification(
                kind=MessageKind.DIGEST,
                confidence=0.85,
                reasons=reasons,
            )

        if TOUR_MESSAGE_RE.search(lowered):
            reasons.append("tour_marker")
            return MessageClassification(
                kind=MessageKind.TOUR_ANNOUNCEMENT,
                confidence=0.8,
                reasons=reasons,
            )

        if EVENT_MESSAGE_RE.search(lowered):
            reasons.append("event_marker")
            return MessageClassification(
                kind=MessageKind.EVENT,
                confidence=0.75,
                reasons=reasons,
            )

        if lowered in LOW_SIGNAL_EXACT_VALUES:
            reasons.append("low_signal_exact")
            return MessageClassification(
                kind=MessageKind.LOW_SIGNAL,
                confidence=0.75,
                reasons=reasons,
            )

        if LOW_SIGNAL_MESSAGE_RE.search(lowered):
            reasons.append("low_signal_marker")
            return MessageClassification(
                kind=MessageKind.LOW_SIGNAL,
                confidence=0.7,
                reasons=reasons,
            )

        if len(lines) <= 2 and len(normalized.split()) <= 3:
            reasons.append("short_low_signal_text")
            return MessageClassification(
                kind=MessageKind.LOW_SIGNAL,
                confidence=0.65,
                reasons=reasons,
            )

        return MessageClassification(
            kind=MessageKind.UNKNOWN,
            confidence=0.3,
            reasons=["fallback_unknown"],
        )
        
