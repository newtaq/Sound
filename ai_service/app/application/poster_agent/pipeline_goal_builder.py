import re
from typing import Any

from app.application.agent_core import AgentToolInput
from app.application.poster_agent.pipeline_models import PosterAgentPipelineRequest


class PosterAgentPipelineGoalBuilder:
    def build_goal(
        self,
        request: PosterAgentPipelineRequest,
        urls_for_verification: list[str],
    ) -> str:
        urls_text = self._build_urls_text(urls_for_verification)
        media_text = self._build_media_goal_text(request)

        return (
            "Из этих данных собери черновик афиши:\n\n"
            f"{request.input_text.strip()}\n\n"
            f"{media_text}"
            "Ссылки, которые нужно проверить:\n"
            f"{urls_text}\n\n"
            "Нужно вывести: тип события, артистов, города, даты, "
            "площадки, ссылки на билеты или официальные источники, "
            "что известно точно из входных данных, что найдено через поиск, "
            "что удалось проверить прямым чтением URL, какие есть конфликты "
            "и чего не хватает для полной публикации.\n\n"
            "Если включён adaptive mode, самостоятельно выбери дополнительные "
            "инструменты, которые нужны для проверки и дополнения афиши."
        )

    def build_required_tools(
        self,
        request: PosterAgentPipelineRequest,
        urls_for_verification: list[str],
    ) -> list[AgentToolInput]:
        tools: list[AgentToolInput] = []

        if request.use_search:
            tools.append(
                AgentToolInput(
                    tool_name="groq_search",
                    arguments={
                        "query": request.search_query
                        or self.build_default_search_query(request.input_text),
                        "context": request.search_context
                        or (
                            "Проверяем данные для черновика афиши. "
                            "Нужно найти только подтверждающую информацию: "
                            "официальные страницы, билеты, площадки, даты. "
                            "Поиск даёт только кандидатов; verified ставит только URL/БД/manual."
                        ),
                    },
                    metadata={
                        "purpose": "find_candidate_sources",
                    },
                )
            )

        if request.use_url_read and urls_for_verification:
            tools.append(
                AgentToolInput(
                    tool_name="url_read",
                    arguments={
                        "urls": urls_for_verification,
                    },
                    metadata={
                        "purpose": "verify_candidate_sources",
                    },
                )
            )

        return tools

    def build_urls_for_verification(
        self,
        request: PosterAgentPipelineRequest,
    ) -> list[str]:
        urls: list[str] = []

        urls.extend(request.verify_urls)
        urls.extend(self.extract_urls_from_text(request.input_text))

        return self._deduplicate_strings(urls)

    def build_visual_debug_metadata(
        self,
        request: PosterAgentPipelineRequest,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        event_title_from_metadata = (
            self._read_metadata_string(request.metadata, "event_title")
            or self._read_metadata_string(request.metadata, "title")
        )
        event_date_from_metadata = (
            self._read_metadata_string(request.metadata, "event_date")
            or self._read_metadata_string(request.metadata, "date")
        )

        event_title = event_title_from_metadata or self.extract_event_title_from_text(
            request.input_text
        )
        event_date = event_date_from_metadata or self.extract_event_date_from_text(
            request.input_text
        )

        if event_title:
            result["event_title"] = event_title
            result["telegram_debug_event_title_source"] = (
                "metadata" if event_title_from_metadata else "input_text"
            )

        if event_date:
            result["event_date"] = event_date
            result["telegram_debug_event_date_source"] = (
                "metadata" if event_date_from_metadata else "input_text"
            )

        return result

    def build_default_search_query(
        self,
        input_text: str,
    ) -> str:
        text = " ".join(
            line.strip()
            for line in input_text.splitlines()
            if line.strip()
        )

        if len(text) > 700:
            text = text[:700].rstrip()

        return f"{text} билеты площадка официальный сайт"

    def extract_urls_from_text(
        self,
        text: str,
    ) -> list[str]:
        pattern = re.compile(
            r"https?://[^\s<>()\[\]{}\"']+",
            flags=re.IGNORECASE,
        )

        urls: list[str] = []

        for match in pattern.finditer(text):
            url = match.group(0).rstrip(".,;:!?)]}")

            if url:
                urls.append(url)

        return urls

    def extract_event_date_from_text(
        self,
        text: str,
    ) -> str | None:
        labeled_patterns = [
            r"(?im)^\s*(?:дата|когда|date|when)\s*[:：\-]\s*(.+?)\s*$",
        ]

        for pattern in labeled_patterns:
            match = re.search(pattern, text)

            if not match:
                continue

            event_date = self._extract_date_from_fragment(match.group(1))

            if event_date:
                return event_date

        return self._extract_date_from_fragment(text)

    def extract_event_title_from_text(
        self,
        text: str,
    ) -> str | None:
        labeled_patterns = [
            r"(?im)^\s*(?:название|событие|мероприятие|title|event)\s*[:：\-]\s*(.+?)\s*$",
            r"(?im)^\s*(?:артист|artist|lineup)\s*[:：\-]\s*(.+?)\s*$",
        ]

        for pattern in labeled_patterns:
            match = re.search(pattern, text)

            if match:
                title = self._clean_title(match.group(1))

                if title:
                    return title

        for line in text.splitlines():
            title = self._clean_title(line)

            if not title:
                continue

            if self._looks_like_non_title_line(title):
                continue

            return title

        return None

    def request_date_has_year(
        self,
        request: PosterAgentPipelineRequest,
    ) -> bool:
        values = [
            request.input_text,
            self._read_metadata_string(request.metadata, "event_date") or "",
            self._read_metadata_string(request.metadata, "date") or "",
        ]

        return any(
            re.search(r"\b20\d{2}\b", value)
            for value in values
        )

    def read_input_event_date(
        self,
        request: PosterAgentPipelineRequest,
    ) -> str | None:
        return (
            self._read_metadata_string(request.metadata, "event_date")
            or self._read_metadata_string(request.metadata, "date")
            or self.extract_event_date_from_text(request.input_text)
        )

    def manual_confirmation_enabled(
        self,
        request: PosterAgentPipelineRequest,
    ) -> bool:
        for key in (
            "manual_confirmed",
            "manual_confirmation",
            "user_confirmed",
            "trusted_manual_input",
        ):
            value = request.metadata.get(key)

            if value is True:
                return True

            if isinstance(value, str) and value.strip().lower() in {
                "true",
                "yes",
                "1",
                "да",
                "истина",
            }:
                return True

        return False

    def _build_media_goal_text(
        self,
        request: PosterAgentPipelineRequest,
    ) -> str:
        if not request.media:
            return ""

        return (
            f"К запросу приложены медиафайлы: {len(request.media)} шт.\n"
            "Если среди них есть афиша или обложка, используй её как входной источник. "
            "Данные из изображения можно считать входными, но не внешне verified.\n\n"
        )

    def _build_urls_text(
        self,
        urls: list[str],
    ) -> str:
        if not urls:
            return "Ссылок для обязательной проверки не найдено."

        return "\n".join(
            f"- {url}"
            for url in urls
        )

    def _extract_date_from_fragment(
        self,
        text: str,
    ) -> str | None:
        iso_match = re.search(
            r"\b(20\d{2})-(0?[1-9]|1[0-2])-([0-2]?\d|3[01])\b",
            text,
        )

        if iso_match:
            year, month, day = iso_match.groups()
            return f"{int(day):02d}.{int(month):02d}.{year}"

        dotted_with_year_match = re.search(
            r"\b([0-2]?\d|3[01])[.\-/](0?[1-9]|1[0-2])[.\-/](20\d{2})\b",
            text,
        )

        if dotted_with_year_match:
            day, month, year = dotted_with_year_match.groups()
            return f"{int(day):02d}.{int(month):02d}.{year}"

        dotted_match = re.search(
            r"\b([0-2]?\d|3[01])[.\-/](0?[1-9]|1[0-2])\b",
            text,
        )

        if dotted_match:
            day, month = dotted_match.groups()
            return f"{int(day):02d}.{int(month):02d}"

        month_match = re.search(
            (
                r"(?i)\b([0-2]?\d|3[01])\s+"
                r"(января|февраля|марта|апреля|мая|июня|июля|"
                r"августа|сентября|октября|ноября|декабря)"
                r"(?:\s+(20\d{2}))?\b"
            ),
            text,
        )

        if not month_match:
            return None

        day, month_name, year = month_match.groups()
        month = {
            "января": "01",
            "февраля": "02",
            "марта": "03",
            "апреля": "04",
            "мая": "05",
            "июня": "06",
            "июля": "07",
            "августа": "08",
            "сентября": "09",
            "октября": "10",
            "ноября": "11",
            "декабря": "12",
        }[month_name.lower()]

        if year:
            return f"{int(day):02d}.{month}.{year}"

        return f"{int(day):02d}.{month}"

    def _clean_title(
        self,
        value: str,
    ) -> str | None:
        cleaned = " ".join(value.strip(" \t\r\n|*-:").split())

        if not cleaned:
            return None

        if len(cleaned) > 80:
            return cleaned[:77].rstrip() + "..."

        return cleaned

    def _looks_like_non_title_line(
        self,
        value: str,
    ) -> bool:
        lowered = value.lower()

        if lowered.startswith(("http://", "https://", "t.me/", "@")):
            return True

        if re.fullmatch(r"[0-3]?\d[.\-/][01]?\d(?:[.\-/]20\d{2})?", value):
            return True

        service_prefixes = (
            "когда",
            "где",
            "дата",
            "адрес",
            "билеты",
            "tickets",
            "date",
            "venue",
            "место",
            "начало",
            "doors",
        )

        return lowered.startswith(service_prefixes)

    def _read_metadata_string(
        self,
        metadata: dict[str, Any],
        key: str,
    ) -> str | None:
        value = metadata.get(key)

        if not isinstance(value, str):
            return None

        stripped = value.strip()

        if not stripped:
            return None

        return stripped

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
    