from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from app.infrastructure.posters.ocr.normalize.phrase_matcher import _canonicalize
from app.infrastructure.posters.ocr.models import EntityCandidate, PosterOCRContext


@dataclass(slots=True)
class EntityNameMatchResult:
    candidate: EntityCandidate
    matched_value: str
    direct_score: float
    canonical_score: float

    @property
    def score(self) -> float:
        return max(self.direct_score, self.canonical_score)


def find_best_entity_name_match(
    text: str,
    context: PosterOCRContext,
    entity_types: tuple[str, ...],
    threshold: float = 0.72,
) -> EntityNameMatchResult | None:
    value = text.strip()
    if not value:
        return None

    normalized_input = _normalize(value)
    canonical_input = _canonicalize(normalized_input)

    best_match: EntityNameMatchResult | None = None
    best_score = threshold

    for candidate in context.entity_candidates:
        if candidate.entity_type not in entity_types:
            continue

        for raw_value in _iter_candidate_values(candidate):
            normalized_candidate = _normalize(raw_value)
            canonical_candidate = _canonicalize(normalized_candidate)

            direct_score = SequenceMatcher(
                None,
                normalized_input,
                normalized_candidate,
            ).ratio()

            canonical_score = SequenceMatcher(
                None,
                canonical_input,
                canonical_candidate,
            ).ratio()

            score = max(direct_score, canonical_score)
            if score <= best_score:
                continue

            best_score = score
            best_match = EntityNameMatchResult(
                candidate=candidate,
                matched_value=raw_value,
                direct_score=direct_score,
                canonical_score=canonical_score,
            )

    return best_match


def _iter_candidate_values(candidate: EntityCandidate) -> list[str]:
    values: list[str] = []

    name = candidate.name.strip()
    if name:
        values.append(name)

    for alias in candidate.aliases:
        alias_value = alias.strip()
        if alias_value:
            values.append(alias_value)

    return values


def _normalize(value: str) -> str:
    return "".join(value.lower().split())

