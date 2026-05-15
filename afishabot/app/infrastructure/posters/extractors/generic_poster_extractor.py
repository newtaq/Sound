from __future__ import annotations

from app.domain.posters.entities.poster_draft import (
    PosterDraft,
    PosterImageRef,
)
from app.domain.posters.entities.poster_input import PosterInput
from app.domain.posters.enums.event_lifecycle_status import (
    EventLifecycleStatus,
)

from app.infrastructure.posters.classifiers.classifier_types import MessageKind
from app.infrastructure.posters.classifiers.message_kind_classifier import (
    MessageKindClassifier,
)
from app.infrastructure.posters.config.channel_profiles import (
    get_channel_profile,
)
from app.infrastructure.posters.extractors.artist_extractor import (
    ArtistExtractor,
)
from app.infrastructure.posters.extractors.description_extractor import (
    DescriptionExtractor,
)
from app.infrastructure.posters.extractors.link_extractor import (
    LinkExtractor,
)
from app.infrastructure.posters.extractors.occurrence_extractor import (
    OccurrenceExtractor,
)
from app.infrastructure.posters.extractors.title_selection import (
    choose_title,
)
from app.infrastructure.posters.patterns.date_patterns import (
    PIPE_OCCURRENCE_RE,
)
from app.infrastructure.posters.semantics.channel_keywords import (
    ORGANIZER_CHANNEL_KEYWORDS,
)
from app.infrastructure.posters.semantics.status_patterns import (
    CANCELLED_RE,
    POSTPONED_RE,
    SOLD_OUT_RE,
)
from app.infrastructure.posters.utils.age_utils import extract_age_limit
from app.infrastructure.posters.utils.entity_normalizer import (
    clean_line,
)
from app.infrastructure.posters.utils.html_text_utils import (
    html_to_text,
)
from app.infrastructure.posters.utils.line_normalizer import (
    normalize_lines,
)
from app.infrastructure.posters.utils.promo_utils import (
    extract_promo_codes,
)
from app.infrastructure.posters.utils.text_utils import (
    normalize_text,
    split_lines,
)


class GenericPosterExtractor:
    def __init__(self) -> None:
        self._artist_extractor = ArtistExtractor()
        self._link_extractor = LinkExtractor()
        self._occurrence_extractor = OccurrenceExtractor()
        self._description_extractor = DescriptionExtractor()
        self._message_kind_classifier = MessageKindClassifier()

    def extract(self, data: PosterInput) -> PosterDraft:
        source_text = html_to_text(data.html_text) if data.html_text else data.text
        normalized_text = normalize_text(source_text)
        lines = self._prepare_lines(normalized_text)

        title = self._extract_title(lines)
        channel_profile = self._resolve_channel_profile(data)
        message_classification = self._message_kind_classifier.classify(normalized_text)

        artist_names = self._artist_extractor.extract(
            lines=lines,
            title=title,
        )

        organizer_names = self._extract_organizer_names(data=data)

        links = self._link_extractor.extract(
            data=data,
            lines=lines,
        )

        promo_codes = extract_promo_codes(normalized_text)

        occurrences = self._occurrence_extractor.extract(
            lines=lines,
            title=title,
            artist_names=artist_names,
            published_at=data.published_at,
            links=links,
        )

        description = self._description_extractor.extract(
            lines=lines,
            title=title,
            artist_names=artist_names,
            occurrences=occurrences,
            promo_codes=promo_codes,
        )

        draft = PosterDraft(
            title=title,
            description=description,
            artist_names=artist_names,
            organizer_names=organizer_names,
            occurrences=occurrences,
            age_limit=extract_age_limit(normalized_text),
            promo_codes=promo_codes,
            ticket_links=links,
            lifecycle_status=self._detect_status(normalized_text),
            source_channel_id=data.channel_id,
            source_post_id=data.post_id,
            images=self._build_image_refs(data),
            raw_text=normalized_text or None,
        )

        self._apply_channel_profile_fallbacks(
            draft=draft,
            channel_profile=channel_profile,
        )

        self._apply_warnings(
            draft=draft,
            message_kind=message_classification.kind,
        )

        return draft

    def _extract_title(self, lines: list[str]) -> str | None:
        title = choose_title(lines)
        if not title:
            return None

        cleaned = clean_line(title)
        if not cleaned:
            return None

        pipe_match = PIPE_OCCURRENCE_RE.match(cleaned)
        if pipe_match:
            artist = clean_line(pipe_match.group("artist"))
            if artist:
                return artist

        return cleaned

    def _prepare_lines(self, text: str) -> list[str]:
        return normalize_lines(split_lines(text))

    def _build_image_refs(self, data: PosterInput) -> list[PosterImageRef]:
        return [
            PosterImageRef(
                telegram_file_id=image.telegram_file_id,
                telegram_file_unique_id=image.telegram_file_unique_id,
                width=image.width,
                height=image.height,
                file_size=image.file_size,
                position=image.position,
            )
            for image in data.images
        ]

    def _detect_status(self, text: str) -> EventLifecycleStatus:
        if CANCELLED_RE.search(text):
            return EventLifecycleStatus.CANCELLED
        if POSTPONED_RE.search(text):
            return EventLifecycleStatus.POSTPONED
        if SOLD_OUT_RE.search(text):
            return EventLifecycleStatus.SOLD_OUT
        return EventLifecycleStatus.ANNOUNCED

    def _extract_organizer_names(self, data: PosterInput) -> list[str]:
        if not data.title:
            return []

        cleaned = clean_line(data.title)
        if not cleaned:
            return []

        lowered = cleaned.casefold()
        if not any(keyword in lowered for keyword in ORGANIZER_CHANNEL_KEYWORDS):
            return []

        return [cleaned]

    def _resolve_channel_profile(self, data: PosterInput):
        return get_channel_profile(
            source_file=None,
            source_channel_id=data.channel_id,
        )

    def _apply_channel_profile_fallbacks(
        self,
        draft: PosterDraft,
        channel_profile,
    ) -> None:
        if channel_profile is None:
            return

        if not draft.occurrences:
            return

        for occurrence in draft.occurrences:
            if occurrence.city_name is None and getattr(channel_profile, "city_name", None):
                occurrence.city_name = channel_profile.city_name

            if occurrence.venue_name is None and getattr(channel_profile, "venue_name", None):
                occurrence.venue_name = channel_profile.venue_name

    def _apply_warnings(
        self,
        draft: PosterDraft,
        message_kind: MessageKind,
    ) -> None:
        if not draft.title:
            draft.warnings.append("Failed to extract title")

        if draft.occurrences:
            return

        warning = self._build_occurrence_warning(message_kind)
        if warning:
            draft.warnings.append(warning)

    def _build_occurrence_warning(
        self,
        message_kind: MessageKind,
    ) -> str:
        if message_kind == MessageKind.PROMO:
            return "Promo post without occurrence data"

        if message_kind == MessageKind.GIVEAWAY:
            return "Giveaway post without occurrence data"

        if message_kind == MessageKind.DIGEST:
            return "Digest post without occurrence data"

        if message_kind == MessageKind.TOUR_ANNOUNCEMENT:
            return "Tour announcement without occurrence data"

        if message_kind == MessageKind.LOW_SIGNAL:
            return "Low-signal post without occurrence data"

        if message_kind == MessageKind.EVENT:
            return "Failed to extract occurrence data for event poster"

        return "Failed to extract occurrence data"
    
