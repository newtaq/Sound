from collections.abc import Mapping, Sequence
from typing import Any


class PosterPostTextRenderer:
    def render(
        self,
        data: Mapping[str, Any],
        template: str | None = None,
    ) -> str:
        event = self._normalize_event(data)

        if template and template.strip():
            return self._render_custom_template(event, template)

        return self._render_default(event)

    def _normalize_event(
        self,
        data: Mapping[str, Any],
    ) -> dict[str, Any]:
        source = self._find_event_source(data)

        return {
            "title": self._read_string(source, "title"),
            "event_type": self._read_string(source, "event_type"),
            "artists": self._read_string_list(source, "artists"),
            "organizers": self._read_string_list(source, "organizers"),
            "age_limit": self._read_age_limit(source),
            "description": self._read_string(source, "description"),
            "occurrences": self._read_occurrences(source),
            "links": self._read_links(source),
            "extra": self._read_extra(source),
        }

    def _find_event_source(
        self,
        data: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        direct_keys = {
            "title",
            "event_type",
            "artists",
            "occurrences",
            "links",
        }

        if any(key in data for key in direct_keys):
            return data

        for key in (
            "verification_result",
            "poster_verification",
            "poster_verification_result",
            "draft",
        ):
            value = data.get(key)

            if isinstance(value, Mapping):
                return value

        agent = data.get("agent")
        if isinstance(agent, Mapping):
            structured_data = agent.get("structured_data")
            if isinstance(structured_data, Mapping):
                for key in (
                    "poster_verification_result",
                    "poster_verification",
                    "verification_result",
                ):
                    value = structured_data.get(key)

                    if isinstance(value, Mapping):
                        return value

        return data

    def _render_default(
        self,
        event: dict[str, Any],
    ) -> str:
        lines: list[str] = []

        title = event["title"] or "Афиша"
        artists = event["artists"]
        description = event["description"]
        age_limit = event["age_limit"]
        occurrences = event["occurrences"]
        links = event["links"]
        extra = event["extra"]

        lines.append(title)

        if artists and not self._title_contains_artists(title, artists):
            lines.append("")
            lines.append(self._join_values(artists))

        if description:
            lines.append("")
            lines.append(description)

        if occurrences:
            lines.append("")
            lines.extend(self._render_occurrences(occurrences))

        if age_limit:
            lines.append("")
            lines.append(f"{age_limit}+")

        useful_extra = [
            item
            for item in extra
            if item and item not in lines
        ]

        if useful_extra:
            lines.append("")
            lines.extend(useful_extra)

        rendered_links = self._render_links(links)

        if rendered_links:
            lines.append("")
            lines.extend(rendered_links)

        return self._clean_result(lines)

    def _render_custom_template(
        self,
        event: dict[str, Any],
        template: str,
    ) -> str:
        occurrences = "\n".join(self._render_occurrences(event["occurrences"]))
        links = "\n".join(self._render_links(event["links"]))

        replacements = {
            "title": event["title"] or "",
            "event_type": event["event_type"] or "",
            "artists": self._join_values(event["artists"]),
            "organizers": self._join_values(event["organizers"]),
            "age_limit": f"{event['age_limit']}+" if event["age_limit"] else "",
            "description": event["description"] or "",
            "occurrences": occurrences,
            "links": links,
            "ticket_url": self._find_first_link_url(event["links"], "ticket") or "",
            "official_url": self._find_first_link_url(event["links"], "official") or "",
            "social_url": self._find_first_link_url(event["links"], "social") or "",
            "extra": "\n".join(event["extra"]),
        }

        result = template

        for key, value in replacements.items():
            result = result.replace("{" + key + "}", value)

        return self._clean_result(result.splitlines())

    def _render_occurrences(
        self,
        occurrences: list[dict[str, Any]],
    ) -> list[str]:
        if len(occurrences) == 1:
            return self._render_single_occurrence(occurrences[0])

        lines = ["Даты:"]

        for occurrence in occurrences:
            text = self._format_occurrence_line(occurrence)
            if text:
                lines.append(f"• {text}")

        return lines

    def _render_single_occurrence(
        self,
        occurrence: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []

        date = occurrence.get("date")
        city = occurrence.get("city")
        venue = occurrence.get("venue")
        address = occurrence.get("address")
        start_time = occurrence.get("start_time")
        doors_time = occurrence.get("doors_time")

        place_parts = [
            value
            for value in (city, venue)
            if value
        ]

        if date:
            lines.append(date)

        if place_parts:
            lines.append(self._join_values(place_parts, separator=" — "))

        if address:
            lines.append(address)

        if doors_time:
            lines.append(f"Двери: {doors_time}")

        if start_time:
            lines.append(f"Начало: {start_time}")

        return lines

    def _format_occurrence_line(
        self,
        occurrence: dict[str, Any],
    ) -> str:
        parts = [
            occurrence.get("date"),
            occurrence.get("city"),
            occurrence.get("venue"),
        ]

        main = self._join_values(
            [
                value
                for value in parts
                if value
            ],
            separator=" — ",
        )

        details: list[str] = []

        if occurrence.get("address"):
            details.append(str(occurrence["address"]))

        if occurrence.get("doors_time"):
            details.append(f"двери {occurrence['doors_time']}")

        if occurrence.get("start_time"):
            details.append(f"начало {occurrence['start_time']}")

        if details:
            return f"{main} ({', '.join(details)})"

        return main

    def _render_links(
        self,
        links: list[dict[str, Any]],
    ) -> list[str]:
        result: list[str] = []

        ticket_url = self._find_first_link_url(links, "ticket")
        official_url = self._find_first_link_url(links, "official")
        social_url = self._find_first_link_url(links, "social")

        if ticket_url:
            result.append(f"Билеты: {ticket_url}")

        if official_url and official_url != ticket_url:
            result.append(f"Подробнее: {official_url}")

        if social_url and social_url not in {ticket_url, official_url}:
            result.append(f"Соцсети: {social_url}")

        used_urls = {
            url
            for url in [ticket_url, official_url, social_url]
            if isinstance(url, str) and url.strip()
        }

        for link in links:
            url = link.get("url")

            if not isinstance(url, str) or not url.strip():
                continue

            url = url.strip()

            if url in used_urls:
                continue

            link_kind = str(
                link.get("kind")
                or link.get("link_type")
                or ""
            ).strip().lower()

            if link_kind in {"ticket", "official", "social"}:
                continue

            result.append(url)
            used_urls.add(url)

        return result

    def _read_occurrences(
        self,
        data: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        value = data.get("occurrences")

        if not isinstance(value, Sequence) or isinstance(value, str):
            return []

        result: list[dict[str, Any]] = []

        for item in value:
            if not isinstance(item, Mapping):
                continue

            occurrence = {
                "city": self._read_string(item, "city_name")
                or self._read_string(item, "city"),
                "venue": self._read_string(item, "venue_name")
                or self._read_string(item, "venue"),
                "address": self._read_string(item, "address"),
                "date": self._read_string(item, "event_date")
                or self._read_string(item, "date"),
                "start_time": self._read_string(item, "start_time")
                or self._read_string(item, "time"),
                "doors_time": self._read_string(item, "doors_time"),
            }

            if any(occurrence.values()):
                result.append(occurrence)

        return result

    def _read_links(
        self,
        data: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        value = data.get("links")

        if not isinstance(value, Sequence) or isinstance(value, str):
            return []

        result: list[dict[str, Any]] = []

        for item in value:
            if isinstance(item, str):
                stripped = item.strip()

                if stripped:
                    result.append(
                        {
                            "url": stripped,
                            "kind": "unknown",
                            "title": None,
                        }
                    )

                continue

            if not isinstance(item, Mapping):
                continue

            url = self._read_string(item, "url")

            if not url:
                continue

            result.append(
                {
                    "url": url,
                    "kind": self._read_string(item, "kind")
                    or self._read_string(item, "link_type")
                    or "unknown",
                    "title": self._read_string(item, "title"),
                }
            )

        return result

    def _read_extra(
        self,
        data: Mapping[str, Any],
    ) -> list[str]:
        result: list[str] = []

        for key in (
            "extra",
            "extra_info",
            "additional_info",
            "notes",
        ):
            value = data.get(key)

            if isinstance(value, str) and value.strip():
                result.append(value.strip())
                continue

            if isinstance(value, Sequence) and not isinstance(value, str):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        result.append(item.strip())

        return self._deduplicate(result)

    def _read_string(
        self,
        data: Mapping[str, Any],
        key: str,
    ) -> str | None:
        value = data.get(key)

        if isinstance(value, str):
            stripped = value.strip()

            if stripped:
                return stripped

        return None

    def _read_string_list(
        self,
        data: Mapping[str, Any],
        key: str,
    ) -> list[str]:
        value = data.get(key)

        if isinstance(value, str):
            stripped = value.strip()

            if stripped:
                return [stripped]

            return []

        if not isinstance(value, Sequence):
            return []

        result: list[str] = []

        for item in value:
            if not isinstance(item, str):
                continue

            stripped = item.strip()

            if stripped:
                result.append(stripped)

        return self._deduplicate(result)

    def _read_age_limit(
        self,
        data: Mapping[str, Any],
    ) -> int | None:
        value = data.get("age_limit")

        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            if value > 0:
                return value

            return None

        if isinstance(value, str):
            digits = "".join(char for char in value if char.isdigit())

            if not digits:
                return None

            try:
                number = int(digits)
            except ValueError:
                return None

            if number > 0:
                return number

        return None

    def _find_first_link_url(
        self,
        links: list[dict[str, Any]],
        kind: str,
    ) -> str | None:
        normalized_kind = kind.strip().lower()

        for link in links:
            link_kind = str(link.get("kind") or "").strip().lower()

            if link_kind != normalized_kind:
                continue

            url = link.get("url")

            if isinstance(url, str) and url.strip():
                return url.strip()

        return None

    def _title_contains_artists(
        self,
        title: str,
        artists: list[str],
    ) -> bool:
        lowered_title = title.lower()

        return any(
            artist.lower() in lowered_title
            for artist in artists
        )

    def _join_values(
        self,
        values: list[str],
        separator: str = ", ",
    ) -> str:
        return separator.join(
            value.strip()
            for value in values
            if value and value.strip()
        )

    def _clean_result(
        self,
        lines: list[str],
    ) -> str:
        result: list[str] = []
        previous_empty = False

        for raw_line in lines:
            line = str(raw_line).strip()

            if not line:
                if result and not previous_empty:
                    result.append("")
                previous_empty = True
                continue

            result.append(line)
            previous_empty = False

        while result and not result[-1]:
            result.pop()

        return "\n".join(result)

    def _deduplicate(
        self,
        values: list[str],
    ) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            key = value.strip().lower()

            if not key or key in seen:
                continue

            seen.add(key)
            result.append(value.strip())

        return result
    