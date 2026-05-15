from app.application.poster_agent.models import (
    PosterAgentDraft,
    PosterAgentDraftStatus,
    PosterAgentIssueSeverity,
    PosterAgentPublishDecision,
    PosterAgentValidationIssue,
)


class PosterAgentDraftValidator:
    def validate(
        self,
        draft: PosterAgentDraft,
    ) -> PosterAgentPublishDecision:
        issues: list[PosterAgentValidationIssue] = []

        self._validate_base_fields(draft, issues)
        self._validate_occurrences(draft, issues)
        self._validate_links(draft, issues)
        self._validate_evidence_metadata(draft, issues)

        draft.validation_issues = issues
        draft.status = self._decide_status(issues)

        return PosterAgentPublishDecision(
            can_publish=draft.status == PosterAgentDraftStatus.READY_TO_PUBLISH,
            status=draft.status,
            reason=self._build_reason(draft.status, issues),
            issues=issues,
            metadata={
                "issue_count": len(issues),
                "critical_count": self._count_by_severity(
                    issues,
                    PosterAgentIssueSeverity.CRITICAL,
                ),
                "error_count": self._count_by_severity(
                    issues,
                    PosterAgentIssueSeverity.ERROR,
                ),
                "warning_count": self._count_by_severity(
                    issues,
                    PosterAgentIssueSeverity.WARNING,
                ),
            },
        )

    def _validate_base_fields(
        self,
        draft: PosterAgentDraft,
        issues: list[PosterAgentValidationIssue],
    ) -> None:
        if not draft.title:
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.CRITICAL,
                    field="title",
                    message="Не найден заголовок афиши.",
                )
            )

        if not draft.artists:
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.CRITICAL,
                    field="artists",
                    message="Не найден артист.",
                )
            )

        if not draft.event_type:
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.WARNING,
                    field="event_type",
                    message="Не определён тип события.",
                )
            )

    def _validate_occurrences(
        self,
        draft: PosterAgentDraft,
        issues: list[PosterAgentValidationIssue],
    ) -> None:
        if not draft.occurrences:
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.CRITICAL,
                    field="occurrences",
                    message="Не найдено ни одной даты/локации события.",
                )
            )
            return

        for index, occurrence in enumerate(draft.occurrences):
            prefix = f"occurrences[{index}]"

            if not occurrence.city:
                issues.append(
                    PosterAgentValidationIssue(
                        severity=PosterAgentIssueSeverity.CRITICAL,
                        field=f"{prefix}.city",
                        message="У события не указан город.",
                    )
                )

            if not occurrence.date:
                issues.append(
                    PosterAgentValidationIssue(
                        severity=PosterAgentIssueSeverity.CRITICAL,
                        field=f"{prefix}.date",
                        message="У события не указана дата.",
                    )
                )

            if not occurrence.venue:
                issues.append(
                    PosterAgentValidationIssue(
                        severity=PosterAgentIssueSeverity.WARNING,
                        field=f"{prefix}.venue",
                        message="Площадка не подтверждена или отсутствует.",
                    )
                )

            if not occurrence.verified:
                issues.append(
                    PosterAgentValidationIssue(
                        severity=PosterAgentIssueSeverity.WARNING,
                        field=prefix,
                        message="Дата/город есть в черновике, но occurrence не подтверждён внешним источником.",
                        metadata={
                            "city": occurrence.city,
                            "date": occurrence.date,
                        },
                    )
                )

            if not occurrence.ticket_links:
                issues.append(
                    PosterAgentValidationIssue(
                        severity=PosterAgentIssueSeverity.WARNING,
                        field=f"{prefix}.ticket_links",
                        message="Нет проверенной ссылки на билеты для события.",
                    )
                )

    def _validate_links(
        self,
        draft: PosterAgentDraft,
        issues: list[PosterAgentValidationIssue],
    ) -> None:
        unverified_ticket_links = [
            link.url
            for link in draft.links
            if link.link_type.value == "ticket" and not link.verified
        ]

        for url in unverified_ticket_links:
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.WARNING,
                    field="links",
                    message="Ссылка на билеты найдена, но не подтверждена.",
                    metadata={
                        "url": url,
                    },
                )
            )

    def _validate_evidence_metadata(
        self,
        draft: PosterAgentDraft,
        issues: list[PosterAgentValidationIssue],
    ) -> None:
        verified_count = int(draft.metadata.get("verified_evidence_count") or 0)
        conflicted_count = int(draft.metadata.get("conflicted_evidence_count") or 0)

        if verified_count == 0:
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.WARNING,
                    field="metadata.verified_evidence_count",
                    message="Нет внешних verified evidence. Черновик нельзя публиковать автоматически.",
                )
            )

        if conflicted_count > 0:
            issues.append(
                PosterAgentValidationIssue(
                    severity=PosterAgentIssueSeverity.ERROR,
                    field="metadata.conflicted_evidence_count",
                    message="Есть конфликтующие evidence-факты.",
                    metadata={
                        "conflicted_evidence_count": conflicted_count,
                    },
                )
            )

    def _decide_status(
        self,
        issues: list[PosterAgentValidationIssue],
    ) -> PosterAgentDraftStatus:
        if any(issue.severity == PosterAgentIssueSeverity.CRITICAL for issue in issues):
            return PosterAgentDraftStatus.BLOCKED

        if any(
            issue.severity in {
                PosterAgentIssueSeverity.ERROR,
                PosterAgentIssueSeverity.WARNING,
            }
            for issue in issues
        ):
            return PosterAgentDraftStatus.NEEDS_REVIEW

        return PosterAgentDraftStatus.READY_TO_PUBLISH

    def _build_reason(
        self,
        status: PosterAgentDraftStatus,
        issues: list[PosterAgentValidationIssue],
    ) -> str:
        if status == PosterAgentDraftStatus.READY_TO_PUBLISH:
            return "Черновик можно публиковать."

        if status == PosterAgentDraftStatus.BLOCKED:
            return "Черновик заблокирован: есть критические ошибки."

        if issues:
            return "Черновик требует ручной проверки."

        return "Черновик создан."

    def _count_by_severity(
        self,
        issues: list[PosterAgentValidationIssue],
        severity: PosterAgentIssueSeverity,
    ) -> int:
        return sum(
            1
            for issue in issues
            if issue.severity == severity
        )
        

