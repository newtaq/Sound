from typing import Any

from app.application.poster_agent.models import (
    PosterAgentDraft,
    PosterAgentLink,
    PosterAgentLinkType,
    PosterAgentPublishDecision,
)
from app.application.poster_agent.verification_enums import (
    PosterAgentFactStatus,
    PosterAgentSourceType,
)
from app.application.poster_agent.verification_models import (
    PosterAgentVerificationResult,
)


class PosterAgentPipelineDraftSync:
    def apply_verification_result(
        self,
        draft: PosterAgentDraft,
        verification_result: PosterAgentVerificationResult,
    ) -> dict[str, Any]:
        metrics = self.build_metrics(verification_result)

        self._sync_draft_metadata(
            draft=draft,
            verification_result=verification_result,
            metrics=metrics,
        )
        self._sync_occurrences(
            draft=draft,
            verification_result=verification_result,
        )
        self._sync_links(
            draft=draft,
            verification_result=verification_result,
        )

        return metrics

    def normalize_decision(
        self,
        decision: PosterAgentPublishDecision,
        verification_result: PosterAgentVerificationResult | None,
        metrics: dict[str, Any] | None = None,
    ) -> PosterAgentPublishDecision:
        if verification_result is None:
            return decision

        effective_metrics = metrics or self.build_metrics(verification_result)

        has_verified_occurrence = effective_metrics["verified_occurrence_count"] > 0
        has_verified_publish_link = (
            effective_metrics["verified_official_link_count"] > 0
            or effective_metrics["verified_ticket_link_count"] > 0
        )
        has_external_evidence = effective_metrics["verified_evidence_count"] > 0

        filtered_issues = []

        for issue in getattr(decision, "issues", []):
            message = self._read_issue_message(issue)

            if (
                has_verified_occurrence
                and (
                    "Дата/город есть в черновике, но occurrence не подтверждён" in message
                    or "Нет подтверждённой даты/города события" in message
                )
            ):
                continue

            if (
                has_external_evidence
                and "Нет внешних verified evidence" in message
            ):
                continue

            if (
                has_verified_publish_link
                and (
                    "Нет проверенной ссылки на билеты для события" in message
                    or "Нет подтверждённой ссылки на билеты или официальный источник" in message
                )
            ):
                continue

            filtered_issues.append(issue)

        try:
            decision.issues = filtered_issues
        except AttributeError:
            pass

        metadata = self._ensure_metadata(decision)
        metadata.update(
            {
                "verified_evidence_count": effective_metrics["verified_evidence_count"],
                "verified_occurrence_count": effective_metrics[
                    "verified_occurrence_count"
                ],
                "verified_official_link_count": effective_metrics[
                    "verified_official_link_count"
                ],
                "verified_ticket_link_count": effective_metrics[
                    "verified_ticket_link_count"
                ],
            }
        )

        return decision

    def build_metrics(
        self,
        verification_result: PosterAgentVerificationResult,
    ) -> dict[str, Any]:
        verified_occurrence_count = sum(
            1
            for occurrence in verification_result.occurrences
            if occurrence.verified and bool(occurrence.source_url)
        )
        verified_official_link_count = sum(
            1
            for link in verification_result.links
            if link.verified and link.kind in {"official", "source"}
        )
        verified_ticket_link_count = sum(
            1
            for link in verification_result.links
            if link.verified and link.kind == "ticket"
        )
        verified_fact_count = sum(
            1
            for fact in verification_result.facts
            if fact.status == PosterAgentFactStatus.VERIFIED
            and fact.source_type
            in {
                PosterAgentSourceType.URL,
                PosterAgentSourceType.DATABASE,
                PosterAgentSourceType.MANUAL,
            }
        )

        verified_evidence_count = (
            verified_occurrence_count
            + verified_official_link_count
            + verified_ticket_link_count
            + verified_fact_count
        )

        unverified_ticket_link_count = sum(
            1
            for link in verification_result.links
            if link.kind == "ticket" and not link.verified
        )

        return {
            "verified_evidence_count": verified_evidence_count,
            "verified_occurrence_count": verified_occurrence_count,
            "verified_official_link_count": verified_official_link_count,
            "verified_ticket_link_count": verified_ticket_link_count,
            "verified_fact_count": verified_fact_count,
            "unverified_ticket_link_count": unverified_ticket_link_count,
        }

    def _sync_draft_metadata(
        self,
        draft: PosterAgentDraft,
        verification_result: PosterAgentVerificationResult,
        metrics: dict[str, Any],
    ) -> None:
        metadata = self._ensure_metadata(draft)

        metadata.update(
            {
                "source": "poster_verification",
                "organizers": verification_result.organizers,
                "overall_confidence": verification_result.overall_confidence,
                "recommendation": verification_result.recommendation.value,
                "missing_fields": verification_result.missing_fields,
                "conflicts": verification_result.conflicts,
                "warnings": verification_result.warnings,
                "explanation": verification_result.explanation,
                **metrics,
            }
        )

    def _sync_occurrences(
        self,
        draft: PosterAgentDraft,
        verification_result: PosterAgentVerificationResult,
    ) -> None:
        verified_ticket_urls = self._verified_ticket_urls(verification_result)

        for index, verification_occurrence in enumerate(
            verification_result.occurrences
        ):
            if index >= len(draft.occurrences):
                continue

            draft_occurrence = draft.occurrences[index]

            self._set_if_present(
                draft_occurrence,
                "city",
                verification_occurrence.city_name,
            )
            self._set_if_present(
                draft_occurrence,
                "date",
                verification_occurrence.event_date,
            )
            self._set_if_present(
                draft_occurrence,
                "venue",
                verification_occurrence.venue_name,
            )
            self._set_if_present(
                draft_occurrence,
                "address",
                verification_occurrence.address,
            )

            if hasattr(draft_occurrence, "verified"):
                draft_occurrence.verified = verification_occurrence.verified

            if hasattr(draft_occurrence, "confidence"):
                draft_occurrence.confidence = self._confidence_label(
                    verification_occurrence.confidence
                )

            if hasattr(draft_occurrence, "ticket_links"):
                existing_ticket_links = getattr(draft_occurrence, "ticket_links", [])
                draft_occurrence.ticket_links = self._merge_ticket_links(
                    existing_ticket_links=existing_ticket_links,
                    extra_ticket_urls=verified_ticket_urls,
                )

            metadata = self._ensure_metadata(draft_occurrence)
            metadata.update(
                {
                    "source_url": verification_occurrence.source_url,
                    "explanation": verification_occurrence.explanation,
                    "start_time": verification_occurrence.start_time,
                    "doors_time": verification_occurrence.doors_time,
                    "confidence_score": verification_occurrence.confidence,
                }
            )

    def _sync_links(
        self,
        draft: PosterAgentDraft,
        verification_result: PosterAgentVerificationResult,
    ) -> None:
        draft_links_by_url = {
            getattr(link, "url", ""): link
            for link in getattr(draft, "links", [])
            if isinstance(getattr(link, "url", None), str)
        }

        for verification_link in verification_result.links:
            draft_link = draft_links_by_url.get(verification_link.url)

            if draft_link is None:
                continue

            self._set_link_type(draft_link, verification_link.kind)
            self._set_if_present(draft_link, "title", verification_link.title)

            if hasattr(draft_link, "verified"):
                draft_link.verified = verification_link.verified

            if hasattr(draft_link, "source"):
                draft_link.source = verification_link.source_type.value

            metadata = self._ensure_metadata(draft_link)
            metadata.update(
                {
                    "confidence": verification_link.confidence,
                    "explanation": verification_link.explanation,
                    "source_type": verification_link.source_type.value,
                }
            )

    def _verified_ticket_urls(
        self,
        verification_result: PosterAgentVerificationResult,
    ) -> list[str]:
        urls: list[str] = []

        for link in verification_result.links:
            if not link.verified:
                continue

            if link.kind != "ticket":
                continue

            urls.append(link.url)

        for fact in verification_result.facts:
            if fact.status != PosterAgentFactStatus.VERIFIED:
                continue

            if fact.field.strip().lower() not in {
                "ticket_link",
                "ticket_url",
            }:
                continue

            if isinstance(fact.value, str) and fact.value.startswith(("http://", "https://")):
                urls.append(fact.value)

        return self._deduplicate_strings(urls)

    def _merge_ticket_links(
        self,
        existing_ticket_links: list[Any],
        extra_ticket_urls: list[str],
    ) -> list[PosterAgentLink]:
        result: list[PosterAgentLink] = []
        seen: set[str] = set()

        for item in existing_ticket_links:
            link = self._coerce_ticket_link(item)

            if link is None:
                continue

            key = link.url.strip().lower()

            if not key or key in seen:
                continue

            seen.add(key)
            result.append(link)

        for url in extra_ticket_urls:
            cleaned_url = str(url or "").strip()

            if not cleaned_url:
                continue

            key = cleaned_url.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(
                PosterAgentLink(
                    url=cleaned_url,
                    link_type=PosterAgentLinkType.TICKET,
                    verified=True,
                    source=PosterAgentSourceType.URL.value,
                    metadata={
                        "source_type": PosterAgentSourceType.URL.value,
                        "added_from_verification": True,
                    },
                )
            )

        return result

    def _coerce_ticket_link(
        self,
        value: Any,
    ) -> PosterAgentLink | None:
        if isinstance(value, PosterAgentLink):
            return value

        if isinstance(value, str):
            url = value.strip()

            if not url:
                return None

            return PosterAgentLink(
                url=url,
                link_type=PosterAgentLinkType.TICKET,
            )

        if isinstance(value, dict):
            raw_url = value.get("url")
            url = raw_url.strip() if isinstance(raw_url, str) else ""

            if not url:
                return None

            raw_link_type = value.get("link_type") or value.get("kind") or "ticket"
            link_type = self._coerce_link_type(raw_link_type)

            return PosterAgentLink(
                url=url,
                link_type=link_type,
                title=value.get("title") if isinstance(value.get("title"), str) else None,
                verified=bool(value.get("verified")),
                source=self._value_to_string(
                    value.get("source") or value.get("source_type")
                ),
                metadata=value.get("metadata") if isinstance(value.get("metadata"), dict) else {},
            )

        raw_url = getattr(value, "url", None)
        url = raw_url.strip() if isinstance(raw_url, str) else ""

        if not url:
            return None

        return PosterAgentLink(
            url=url,
            link_type=self._coerce_link_type(getattr(value, "link_type", "ticket")),
            title=getattr(value, "title", None),
            verified=bool(getattr(value, "verified", False)),
            source=self._value_to_string(getattr(value, "source", None)),
            metadata=getattr(value, "metadata", None) or {},
        )

    def _coerce_link_type(
        self,
        value: Any,
    ) -> PosterAgentLinkType:
        raw_value = self._value_to_string(value) or "ticket"

        try:
            return PosterAgentLinkType(raw_value)
        except ValueError:
            return PosterAgentLinkType.TICKET

    def _value_to_string(
        self,
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        enum_value = getattr(value, "value", None)

        if enum_value is not None:
            return str(enum_value)

        return str(value)

    def _read_issue_message(
        self,
        issue: Any,
    ) -> str:
        if isinstance(issue, dict):
            value = issue.get("message")

            if isinstance(value, str):
                return value

            return ""

        value = getattr(issue, "message", "")

        if isinstance(value, str):
            return value

        return ""

    def _confidence_label(
        self,
        confidence: float,
    ) -> str:
        if confidence >= 0.85:
            return "high"

        if confidence >= 0.55:
            return "medium"

        return "low"

    def _set_link_type(
        self,
        draft_link: Any,
        link_type: str,
    ) -> None:
        if not hasattr(draft_link, "link_type"):
            return

        current_value = getattr(draft_link, "link_type", None)

        if hasattr(current_value, "value"):
            enum_type = type(current_value)

            try:
                draft_link.link_type = enum_type(link_type)
            except ValueError:
                return

            return

        draft_link.link_type = link_type

    def _set_if_present(
        self,
        obj: Any,
        name: str,
        value: Any,
    ) -> None:
        if value is None:
            return

        if not hasattr(obj, name):
            return

        setattr(obj, name, value)

    def _ensure_metadata(
        self,
        obj: Any,
    ) -> dict[str, Any]:
        metadata = getattr(obj, "metadata", None)

        if isinstance(metadata, dict):
            return metadata

        metadata = {}

        try:
            setattr(obj, "metadata", metadata)
        except AttributeError:
            pass

        return metadata

    def _deduplicate_strings(
        self,
        values: list[str],
    ) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            normalized = value.strip()

            if not normalized:
                continue

            key = normalized.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(normalized)

        return result
    