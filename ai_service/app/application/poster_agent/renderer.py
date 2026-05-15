from app.application.poster_agent.models import (
    PosterAgentDraft,
    PosterAgentDraftStatus,
    PosterAgentIssueSeverity,
    PosterAgentPublishDecision,
)


class PosterAgentRenderer:
    def render_review_text(
        self,
        draft: PosterAgentDraft,
        decision: PosterAgentPublishDecision,
    ) -> str:
        parts: list[str] = []

        parts.append(self._render_header(draft, decision))
        parts.append(self._render_main_info(draft))
        parts.append(self._render_occurrences(draft))
        parts.append(self._render_links(draft))
        parts.append(self._render_candidate_links(draft))
        parts.append(self._render_decision(decision))
        parts.append(self._render_issues(decision))

        return "\n\n".join(
            part
            for part in parts
            if part.strip()
        ).strip()

    def _render_header(
        self,
        draft: PosterAgentDraft,
        decision: PosterAgentPublishDecision,
    ) -> str:
        if decision.can_publish:
            icon = "✅"
            status_text = "готово к публикации"
        elif draft.status == PosterAgentDraftStatus.BLOCKED:
            icon = "⛔"
            status_text = "заблокировано"
        else:
            icon = "📝"
            status_text = "нужна проверка"

        return f"{icon} Черновик афиши: {status_text}"

    def _render_main_info(
        self,
        draft: PosterAgentDraft,
    ) -> str:
        lines: list[str] = []

        if draft.title:
            lines.append(f"Название: {draft.title}")

        if draft.event_type:
            lines.append(f"Тип: {draft.event_type}")

        if draft.artists:
            lines.append(f"Артисты: {', '.join(draft.artists)}")

        if draft.age_limit is not None:
            lines.append(f"Возраст: {draft.age_limit}+")

        if not lines:
            return ""

        return "\n".join(lines)

    def _render_occurrences(self, draft) -> str:
        occurrences = getattr(draft, "occurrences", None) or []

        if not occurrences:
            return "Даты и города:\n⚠️ Не найдены"

        lines: list[str] = ["Даты и города:"]

        for occurrence in occurrences:
            verified = bool(getattr(occurrence, "verified", False))
            marker = "✅" if verified else "⚠️"

            date = self._get_value(occurrence, "date")
            city = self._get_value(occurrence, "city")
            venue = self._get_value(occurrence, "venue")
            time = self._get_value(occurrence, "time")
            address = self._get_value(occurrence, "address")

            main_parts = [
                value
                for value in [date, city, venue]
                if value
            ]

            if main_parts:
                line = f"{marker} {' — '.join(main_parts)}"
            else:
                line = f"{marker} Дата/город/площадка не определены"

            if time:
                line += f" — {time}"

            lines.append(line)

            if address:
                lines.append(f"   Адрес: {address}")

            ticket_links = getattr(occurrence, "ticket_links", None) or []
            for ticket_link in ticket_links:
                link_url = self._link_url(ticket_link)
                if not link_url:
                    continue

                link_marker = "✅" if self._link_verified(ticket_link) else "⚠️"
                link_title = self._link_title(ticket_link)

                if link_title:
                    lines.append(f"   {link_marker} Билеты: {link_url} — {link_title}")
                else:
                    lines.append(f"   {link_marker} Билеты: {link_url}")

        return "\n".join(lines)

    def _get_value(self, item, field_name: str) -> str | None:
        if item is None:
            return None

        if isinstance(item, dict):
            value = item.get(field_name)
        else:
            value = getattr(item, field_name, None)

        if value is None:
            return None

        value = str(value).strip()
        return value or None

    def _link_url(self, link) -> str | None:
        if link is None:
            return None

        if isinstance(link, str):
            value = link
        elif isinstance(link, dict):
            value = link.get("url")
        else:
            value = getattr(link, "url", None)

        if value is None:
            return None

        value = str(value).strip()
        return value or None

    def _link_title(self, link) -> str | None:
        if link is None or isinstance(link, str):
            return None

        if isinstance(link, dict):
            value = link.get("title")
        else:
            value = getattr(link, "title", None)

        if value is None:
            return None

        value = str(value).strip()
        return value or None

    def _link_verified(self, link) -> bool:
        if link is None or isinstance(link, str):
            return False

        if isinstance(link, dict):
            return bool(link.get("verified"))

        return bool(getattr(link, "verified", False))

    def _render_links(
        self,
        draft: PosterAgentDraft,
    ) -> str:
        if not draft.links:
            return ""

        lines = ["Ссылки:"]

        for link in draft.links:
            marker = "✅" if link.verified else "⚠️"
            title = f" — {link.title}" if link.title else ""
            lines.append(f"{marker} {link.link_type.value}: {link.url}{title}")

        return "\n".join(lines)

    def _render_candidate_links(
        self,
        draft: PosterAgentDraft,
    ) -> str:
        candidate_links = draft.metadata.get("candidate_links")

        if not isinstance(candidate_links, list) or not candidate_links:
            return ""

        lines = ["Непроверенные ссылки-кандидаты:"]

        for candidate in candidate_links:
            if not isinstance(candidate, dict):
                continue

            url = str(candidate.get("url") or "").strip()
            link_type = str(candidate.get("link_type") or "other").strip()
            evidence_status = str(candidate.get("evidence_status") or "unknown").strip()

            if not url:
                continue

            lines.append(f"⚠️ {link_type}: {url} ({evidence_status})")

        if len(lines) == 1:
            return ""

        return "\n".join(lines)

    def _render_decision(
        self,
        decision: PosterAgentPublishDecision,
    ) -> str:
        can_publish = "да" if decision.can_publish else "нет"

        return "\n".join(
            [
                "Решение:",
                f"Можно публиковать: {can_publish}",
                f"Статус: {decision.status.value}",
                f"Причина: {decision.reason}",
            ]
        )

    def _render_issues(
        self,
        decision: PosterAgentPublishDecision,
    ) -> str:
        if not decision.issues:
            return ""

        grouped = self._group_issue_messages(decision)

        lines = ["Что нужно проверить:"]

        for severity in [
            PosterAgentIssueSeverity.CRITICAL,
            PosterAgentIssueSeverity.ERROR,
            PosterAgentIssueSeverity.WARNING,
            PosterAgentIssueSeverity.INFO,
        ]:
            for message, count in grouped.get(severity, []):
                icon = self._issue_icon(severity)
                suffix = f" ×{count}" if count > 1 else ""
                lines.append(f"{icon} {message}{suffix}")

        return "\n".join(lines)

    def _group_issue_messages(
        self,
        decision: PosterAgentPublishDecision,
    ) -> dict[PosterAgentIssueSeverity, list[tuple[str, int]]]:
        grouped: dict[PosterAgentIssueSeverity, dict[str, int]] = {}

        for issue in decision.issues:
            grouped.setdefault(issue.severity, {})
            grouped[issue.severity][issue.message] = (
                grouped[issue.severity].get(issue.message, 0) + 1
            )

        return {
            severity: list(messages.items())
            for severity, messages in grouped.items()
        }

    def _issue_icon(
        self,
        severity: PosterAgentIssueSeverity,
    ) -> str:
        if severity == PosterAgentIssueSeverity.CRITICAL:
            return "⛔"

        if severity == PosterAgentIssueSeverity.ERROR:
            return "⛔"

        if severity == PosterAgentIssueSeverity.WARNING:
            return "⚠️"

        return "ℹ️"
    

