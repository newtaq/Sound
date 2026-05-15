from dataclasses import dataclass, field


@dataclass(slots=True)
class AIContentRegistry:
    content_types: list[str] = field(default_factory=lambda: [
        "event_announcement",
        "tour_announcement",
        "event_update",
        "tour_update",
        "event_promo",
        "event_reminder",
        "event_recap",
        "event_cancelled",
        "event_postponed",
        "ticket_update",
        "lineup_update",
        "venue_update",
        "trash",
        "unknown",
    ])
    priorities: list[str] = field(default_factory=lambda: [
        "critical",
        "high",
        "medium",
        "low",
        "trash",
    ])
    decision_types: list[str] = field(default_factory=lambda: [
        "create_event_candidate",
        "create_tour_candidate",
        "update_event",
        "update_tour",
        "attach_promo",
        "attach_reminder",
        "attach_recap_media",
        "mark_event_cancelled",
        "mark_event_postponed",
        "update_tickets",
        "update_lineup",
        "update_venue",
        "ignore",
        "needs_review",
    ])

    def add_content_type(self, value: str) -> None:
        self._add_unique(self.content_types, value)

    def add_priority(self, value: str) -> None:
        self._add_unique(self.priorities, value)

    def add_decision_type(self, value: str) -> None:
        self._add_unique(self.decision_types, value)

    def _add_unique(self, values: list[str], value: str) -> None:
        normalized = value.strip()
        if normalized and normalized not in values:
            values.append(normalized)
            

