from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PosterEventSummaryRenderer:
    def render(
        self,
        verification_data: dict[str, Any],
        status: str | None = None,
    ) -> str:
        if not isinstance(verification_data, dict):
            return ""

        title = self._read_string(verification_data, "title") or "Без названия"
        status_text = self._build_status_text(status, verification_data)

        parts: list[str] = [
            f"🎫 Афиша: {title}",
            "",
            f"Статус: {status_text}",
            "",
            "Событие:",
        ]

        parts.extend(self._build_event_lines(verification_data))

        link_lines = self._build_link_lines(verification_data)
        if link_lines:
            parts.extend(["", "Ссылки:"])
            parts.extend(link_lines)

        conflict_lines = self._build_conflict_lines(verification_data)
        if conflict_lines:
            parts.extend(["", "Конфликты:"])
            parts.extend(conflict_lines)

        missing_lines = self._build_missing_lines(verification_data)
        if missing_lines:
            parts.extend(["", "Чего не хватает:"])
            parts.extend(missing_lines)

        return "\n".join(parts).strip()

    def _build_status_text(
        self,
        status: str | None,
        data: dict[str, Any],
    ) -> str:
        raw = status or self._read_string(data, "recommendation")

        if not raw:
            return "нужна проверка"

        value = raw.strip().lower()

        if value in {"auto_publish", "ready", "can_publish", "publish"}:
            return "можно публиковать"

        if value in {"blocked", "reject", "rejected"}:
            return "нельзя публиковать"

        return "нужна проверка"

    def _build_event_lines(
        self,
        data: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []

        self._append_value_line(
            lines=lines,
            label="Тип",
            value=self._event_type_label(self._read_string(data, "event_type")),
            verified=True,
        )

        artists = self._read_string_list(data, "artists")
        if artists:
            self._append_value_line(
                lines=lines,
                label="Артист",
                value=", ".join(artists),
                verified=self._is_fact_verified(data, "artist"),
            )

        occurrences = self._read_dict_list(data, "occurrences")
        if occurrences:
            occurrence = occurrences[0]

            self._append_value_line(
                lines=lines,
                label="Дата",
                value=self._read_string(occurrence, "event_date"),
                verified=self._is_occurrence_verified(occurrence)
                or self._is_fact_verified(data, "date"),
                note=self._fact_note(data, "date"),
            )
            self._append_value_line(
                lines=lines,
                label="Город",
                value=self._read_string(occurrence, "city_name"),
                verified=self._is_occurrence_verified(occurrence)
                or self._is_fact_verified(data, "city"),
                note=self._fact_note(data, "city"),
            )
            self._append_value_line(
                lines=lines,
                label="Площадка",
                value=self._read_string(occurrence, "venue_name"),
                verified=self._is_occurrence_verified(occurrence)
                or self._is_fact_verified(data, "venue"),
                note=self._fact_note(data, "venue"),
            )
            self._append_value_line(
                lines=lines,
                label="Адрес",
                value=self._read_string(occurrence, "address"),
                verified=self._is_occurrence_verified(occurrence)
                or self._is_fact_verified(data, "address"),
                note=self._fact_note(data, "address"),
            )

            start_time = self._read_string(occurrence, "start_time")
            doors_time = self._read_string(occurrence, "doors_time")

            if start_time:
                self._append_value_line(
                    lines=lines,
                    label="Начало",
                    value=start_time,
                    verified=self._is_fact_verified(data, "start_time"),
                    note=self._fact_note(data, "start_time"),
                )

            if doors_time:
                self._append_value_line(
                    lines=lines,
                    label="Двери",
                    value=doors_time,
                    verified=self._is_fact_verified(data, "doors_time"),
                    note=self._fact_note(data, "doors_time"),
                )

        age_limit = self._read_age_limit(data)
        if age_limit:
            self._append_value_line(
                lines=lines,
                label="Возраст",
                value=age_limit,
                verified=self._is_fact_verified(data, "age_limit"),
                note=self._fact_note(data, "age_limit") or "из афиши, не подтверждено внешним источником",
            )

        price = self._read_fact_value(data, "price")
        if price:
            self._append_value_line(
                lines=lines,
                label="Цена",
                value=price,
                verified=self._is_fact_verified(data, "price"),
                note=self._fact_note(data, "price") or "из текста, не подтверждено",
            )

        return lines

    def _build_link_lines(
        self,
        data: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []

        for link in self._read_dict_list(data, "links"):
            url = self._read_string(link, "url")
            if not url:
                continue

            kind = self._read_string(link, "kind") or "link"
            title = self._read_string(link, "title")
            verified = self._read_bool(link, "verified")
            note = self._read_string(link, "explanation")

            label = self._link_label(kind)
            text = url

            if title:
                text = f"{url} — {title}"

            self._append_value_line(
                lines=lines,
                label=label,
                value=text,
                verified=verified,
                note=note if not verified else None,
            )

        return lines

    def _build_confirmed_lines(
        self,
        data: dict[str, Any],
    ) -> list[str]:
        result: list[str] = []

        confirmed_facts: list[str] = []
        for fact in self._read_dict_list(data, "facts"):
            if not self._is_verified_fact(fact):
                continue

            label = self._fact_label(self._read_string(fact, "field"))
            value = self._read_string(fact, "value")

            if label and value:
                confirmed_facts.append(f"{label}: {value}")

        if confirmed_facts:
            for item in confirmed_facts:
                result.append(f"✅ {item}")

        for occurrence in self._read_dict_list(data, "occurrences"):
            if not self._is_occurrence_verified(occurrence):
                continue

            source_url = self._read_string(occurrence, "source_url")
            venue = self._read_string(occurrence, "venue_name")
            city = self._read_string(occurrence, "city_name")
            date = self._read_string(occurrence, "event_date")

            summary = self._join_non_empty([date, city, venue], " — ")
            if summary:
                if source_url:
                    result.append(f"✅ Дата/город/площадка подтверждены: {summary} ({source_url})")
                else:
                    result.append(f"✅ Дата/город/площадка подтверждены: {summary}")

        for link in self._read_dict_list(data, "links"):
            if not self._read_bool(link, "verified"):
                continue

            url = self._read_string(link, "url")
            kind = self._link_label(self._read_string(link, "kind"))

            if url:
                result.append(f"✅ {kind} подтверждён: {url}")

        return self._deduplicate(result)

    def _build_unconfirmed_lines(
        self,
        data: dict[str, Any],
    ) -> list[str]:
        result: list[str] = []

        for fact in self._read_dict_list(data, "facts"):
            if self._is_verified_fact(fact):
                continue

            field = self._read_string(fact, "field")
            value = self._read_string(fact, "value")
            label = self._fact_label(field)
            explanation = self._read_string(fact, "explanation")

            if not label or not value:
                continue

            if explanation:
                result.append(f"⚠️ {label}: {value} — {explanation}")
            else:
                result.append(f"⚠️ {label}: {value}")

        for link in self._read_dict_list(data, "links"):
            if self._read_bool(link, "verified"):
                continue

            url = self._read_string(link, "url")
            kind = self._link_label(self._read_string(link, "kind"))
            explanation = self._read_string(link, "explanation")

            if not url:
                continue

            if explanation:
                result.append(f"⚠️ {kind}: {url} — {explanation}")
            else:
                result.append(f"⚠️ {kind}: {url}")

        return self._deduplicate(result)

    def _build_conflict_lines(
        self,
        data: dict[str, Any],
    ) -> list[str]:
        conflicts = self._read_list(data, "conflicts")
        result: list[str] = []

        for conflict in conflicts:
            if isinstance(conflict, str) and conflict.strip():
                result.append(f"❌ {conflict.strip()}")
            elif isinstance(conflict, dict):
                text = (
                    self._read_string(conflict, "message")
                    or self._read_string(conflict, "explanation")
                    or self._read_string(conflict, "field")
                )

                if text:
                    result.append(f"❌ {text}")

        return result

    def _build_missing_lines(
        self,
        data: dict[str, Any],
    ) -> list[str]:
        missing = self._read_list(data, "missing_fields")
        result: list[str] = []

        for item in missing:
            if isinstance(item, str) and item.strip():
                result.append(f"⚠️ {self._fact_label(item) or item.strip()}")
            elif isinstance(item, dict):
                field = self._read_string(item, "field") or self._read_string(item, "name")
                explanation = self._read_string(item, "explanation")

                if field and explanation:
                    result.append(f"⚠️ {self._fact_label(field) or field} — {explanation}")
                elif field:
                    result.append(f"⚠️ {self._fact_label(field) or field}")

        return result

    def _append_value_line(
        self,
        lines: list[str],
        label: str,
        value: str | None,
        verified: bool,
        note: str | None = None,
    ) -> None:
        if not value:
            return

        icon = "✅" if verified else "⚠️"
        text = f"{icon} {label}: {value}"

        if note and not verified:
            text = f"{text} — {note}"

        lines.append(text)

    def _read_age_limit(
        self,
        data: dict[str, Any],
    ) -> str | None:
        value = data.get("age_limit")

        if value is None:
            return self._read_fact_value(data, "age_limit")

        if isinstance(value, int):
            return f"{value}+"

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None

            if stripped.endswith("+"):
                return stripped

            if stripped.isdigit():
                return f"{stripped}+"

            return stripped

        return None

    def _is_fact_verified(
        self,
        data: dict[str, Any],
        field: str,
    ) -> bool:
        target = field.strip().lower()

        for fact in self._read_dict_list(data, "facts"):
            fact_field = (self._read_string(fact, "field") or "").strip().lower()

            if fact_field != target:
                continue

            return self._is_verified_fact(fact)

        return False

    def _is_verified_fact(
        self,
        fact: dict[str, Any],
    ) -> bool:
        status = (self._read_string(fact, "status") or "").strip().lower()
        return status == "verified"

    def _fact_note(
        self,
        data: dict[str, Any],
        field: str,
    ) -> str | None:
        target = field.strip().lower()

        for fact in self._read_dict_list(data, "facts"):
            fact_field = (self._read_string(fact, "field") or "").strip().lower()

            if fact_field != target:
                continue

            if self._is_verified_fact(fact):
                return None

            return self._read_string(fact, "explanation")

        return None

    def _read_fact_value(
        self,
        data: dict[str, Any],
        field: str,
    ) -> str | None:
        target = field.strip().lower()

        for fact in self._read_dict_list(data, "facts"):
            fact_field = (self._read_string(fact, "field") or "").strip().lower()

            if fact_field == target:
                return self._read_string(fact, "value")

        return None

    def _is_occurrence_verified(
        self,
        occurrence: dict[str, Any],
    ) -> bool:
        return self._read_bool(occurrence, "verified")

    def _event_type_label(
        self,
        value: str | None,
    ) -> str | None:
        if not value:
            return None

        normalized = value.strip().lower()

        labels = {
            "concert": "концерт",
            "festival": "фестиваль",
            "party": "вечеринка",
            "show": "шоу",
            "performance": "спектакль",
            "meetup": "встреча",
        }

        return labels.get(normalized, value.strip())

    def _link_label(
        self,
        value: str | None,
    ) -> str:
        if not value:
            return "Ссылка"

        normalized = value.strip().lower()

        labels = {
            "ticket": "Билеты",
            "tickets": "Билеты",
            "official": "Официальный источник",
            "social": "Telegram-канал",
            "telegram": "Telegram-канал",
            "vk": "VK",
            "site": "Сайт",
        }

        return labels.get(normalized, value.strip())

    def _fact_label(
        self,
        value: str | None,
    ) -> str | None:
        if not value:
            return None

        normalized = value.strip().lower()

        labels = {
            "artist": "Артист",
            "artists": "Артист",
            "city": "Город",
            "date": "Дата",
            "event_date": "Дата",
            "venue": "Площадка",
            "venue_name": "Площадка",
            "address": "Адрес",
            "age_limit": "Возраст",
            "price": "Цена",
            "ticket_link": "Билеты",
            "official_source": "Официальный источник",
            "start_time": "Начало",
            "doors_time": "Двери",
        }

        return labels.get(normalized, value.strip())

    def _read_string(
        self,
        data: dict[str, Any],
        key: str,
    ) -> str | None:
        value = data.get(key)

        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None

        if isinstance(value, int | float):
            return str(value)

        return None

    def _read_bool(
        self,
        data: dict[str, Any],
        key: str,
    ) -> bool:
        value = data.get(key)

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "1", "да"}

        return False

    def _read_list(
        self,
        data: dict[str, Any],
        key: str,
    ) -> list[Any]:
        value = data.get(key)

        if isinstance(value, list):
            return value

        return []

    def _read_dict_list(
        self,
        data: dict[str, Any],
        key: str,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for item in self._read_list(data, key):
            if isinstance(item, dict):
                result.append(item)

        return result

    def _read_string_list(
        self,
        data: dict[str, Any],
        key: str,
    ) -> list[str]:
        result: list[str] = []

        for item in self._read_list(data, key):
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, int | float):
                result.append(str(item))

        return result

    def _join_non_empty(
        self,
        values: list[str | None],
        separator: str,
    ) -> str:
        return separator.join(
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        )

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
            result.append(value)

        return result
    