import json
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from app.application.agent_core.evidence import (
    AgentEvidence,
    AgentEvidenceSet,
    EvidenceConfidence,
    EvidenceSource,
    EvidenceStatus,
)
from app.application.agent_core.tools import AgentToolOutput
from app.application.ai_client import AIClient
from app.application.contracts import AIResponseStatus


@dataclass(slots=True)
class EvidenceExtractionRequest:
    goal: str
    tool_outputs: list[AgentToolOutput] = field(default_factory=list)
    provider_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceExtractor:
    def __init__(
        self,
        ai_client: AIClient,
    ) -> None:
        self._ai_client = ai_client

    async def extract(
        self,
        request: EvidenceExtractionRequest,
    ) -> AgentEvidenceSet:
        if not request.tool_outputs:
            return AgentEvidenceSet()

        response = await self._ai_client.ask(
            text=self._build_prompt(request),
            provider_name=request.provider_name,
            instructions=self._build_instructions(),
            response_format="json",
            use_history=False,
            save_history=False,
            metadata={
                **request.metadata,
                "evidence_extraction": True,
            },
        )

        if response.status != AIResponseStatus.OK:
            return AgentEvidenceSet()

        data = self._parse_json(response.text)
        evidence_set = self._build_evidence_set(data)

        evidence_set = self._normalize_by_tool_outputs(
            evidence_set=evidence_set,
            tool_outputs=request.tool_outputs,
        )

        if evidence_set.items:
            return evidence_set

        return self._build_deterministic_evidence_from_tools(
            tool_outputs=request.tool_outputs,
        )

    def _build_instructions(self) -> str:
        return (
            "Ты извлекаешь проверяемые факты из результатов инструментов. "
            "Не добавляй факты, которых нет в тексте. "
            "Очень важно: результат web/search-модели сам по себе НЕ является полной верификацией. "
            "Если факт взят только из текста инструмента groq_search, помечай его как unverified. "
            "Для groq_search confidence не выше medium, если нет прямого проверенного URL-источника. "
            "Статус verified можно ставить только если в тексте есть конкретный source_url "
            "и ясно, что факт напрямую подтверждён этим источником, либо если источник имеет тип db, "
            "url_read, url_parser или manual_confirmed. "
            "Если URL был заблокирован антиботом, не помечай связанные факты как verified. "
            "Если факт основан на предположении, формулировке вроде 'уточняется', 'например', 'обычно', "
            "'можно увидеть после перехода', помечай его как unverified и confidence low. "
            "Если разные фрагменты дают разные площадки, даты, города или ссылки, помечай такие факты как conflicted. "
            "Верни только JSON без markdown."
        )

    def _build_prompt(
        self,
        request: EvidenceExtractionRequest,
    ) -> str:
        tool_texts: list[str] = []

        for index, tool_output in enumerate(request.tool_outputs, start=1):
            tool_texts.append(
                "\n".join(
                    [
                        f"TOOL #{index}: {tool_output.tool_name}",
                        f"OK: {tool_output.ok}",
                        f"ERROR: {tool_output.error or '-'}",
                        "DATA:",
                        str(tool_output.data),
                    ]
                )
            )

        tool_text = "\n\n".join(tool_texts)

        return (
            "Задача агента:\n"
            f"{request.goal.strip()}\n\n"
            "Результаты инструментов:\n"
            f"{tool_text}\n\n"
            "Извлеки проверяемые факты в JSON такого вида:\n"
            "{\n"
            '  "items": [\n'
            "    {\n"
            '      "field": "artist|city|date|venue|ticket_link|official_source|price|time|age_limit|other",\n'
            '      "value": "значение",\n'
            '      "confidence": "low|medium|high",\n'
            '      "status": "unverified|verified|conflicted|rejected",\n'
            '      "source_type": "search|url_read|url_parser|ocr|db|user_input|manual_confirmed|other",\n'
            '      "source_title": "название источника или null",\n'
            '      "source_url": "url или null",\n'
            '      "raw_text": "короткий фрагмент текста-основания",\n'
            '      "explanation": "почему такой статус"\n'
            "    }\n"
            "  ]\n"
            "}"
        )

    def _parse_json(
        self,
        text: str,
    ) -> dict[str, Any]:
        value = text.strip()

        if value.startswith("```"):
            value = value.strip("`").strip()
            if value.lower().startswith("json"):
                value = value[4:].strip()

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"items": []}

        if not isinstance(parsed, dict):
            return {"items": []}

        return parsed

    def _build_evidence_set(
        self,
        data: dict[str, Any],
    ) -> AgentEvidenceSet:
        evidence_set = AgentEvidenceSet()

        items = data.get("items")
        if not isinstance(items, list):
            return evidence_set

        for item in items:
            if not isinstance(item, dict):
                continue

            evidence = self._build_evidence(item)
            if evidence is not None:
                evidence_set.add(evidence)

        return evidence_set

    def _normalize_by_tool_outputs(
        self,
        evidence_set: AgentEvidenceSet,
        tool_outputs: list[AgentToolOutput],
    ) -> AgentEvidenceSet:
        url_read_pages = self._collect_url_read_pages(tool_outputs)

        if not url_read_pages:
            return evidence_set

        blocked_urls = {
            self._normalize_url_for_compare(page.get("url"))
            for page in url_read_pages
            if page.get("blocked_by_antibot") is True
        }
        blocked_urls.update(
            self._normalize_url_for_compare(page.get("final_url"))
            for page in url_read_pages
            if page.get("blocked_by_antibot") is True
        )
        blocked_urls.discard("")

        readable_pages: dict[str, dict[str, Any]] = {}

        for page in url_read_pages:
            if page.get("ok") is not True:
                continue

            for key in ["url", "final_url"]:
                normalized_url = self._normalize_url_for_compare(page.get(key))
                if normalized_url:
                    readable_pages[normalized_url] = page

        for evidence in evidence_set.items:
            self._normalize_single_evidence_by_urls(
                evidence=evidence,
                blocked_urls=blocked_urls,
                readable_pages=readable_pages,
            )

        return evidence_set

    def _collect_url_read_pages(
        self,
        tool_outputs: list[AgentToolOutput],
    ) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []

        for tool_output in tool_outputs:
            if tool_output.tool_name != "url_read":
                continue

            if not isinstance(tool_output.data, dict):
                continue

            raw_pages = tool_output.data.get("pages")

            if not isinstance(raw_pages, list):
                continue

            for page in raw_pages:
                if isinstance(page, dict):
                    pages.append(page)

        return pages

    def _build_deterministic_evidence_from_tools(
        self,
        tool_outputs: list[AgentToolOutput],
    ) -> AgentEvidenceSet:
        evidence_set = AgentEvidenceSet()

        for page in self._collect_url_read_pages(tool_outputs):
            url = self._read_page_url(page)

            if url is None:
                continue

            field = self._guess_url_evidence_field(url)

            if page.get("ok") is True:
                evidence_set.add(
                    AgentEvidence(
                        field=field,
                        value=url,
                        confidence=EvidenceConfidence.MEDIUM,
                        status=EvidenceStatus.VERIFIED,
                        source=EvidenceSource(
                            source_type="url_read",
                            title=self._read_page_title(page),
                            url=url,
                            raw_text=self._read_page_raw_text(page),
                            metadata={
                                "url_read_ok": True,
                                "status_code": page.get("status_code"),
                                "final_url": page.get("final_url"),
                                "deterministic_evidence": True,
                            },
                        ),
                        explanation="URL successfully read by url_read.",
                        metadata={
                            "deterministic_evidence": True,
                        },
                    )
                )
                continue

            if page.get("blocked_by_antibot") is True:
                evidence_set.add(
                    AgentEvidence(
                        field=field,
                        value=url,
                        confidence=EvidenceConfidence.LOW,
                        status=EvidenceStatus.UNVERIFIED,
                        source=EvidenceSource(
                            source_type="url_read",
                            title=self._read_page_title(page),
                            url=url,
                            raw_text=self._read_page_raw_text(page),
                            metadata={
                                "url_read_ok": False,
                                "blocked_by_antibot": True,
                                "status_code": page.get("status_code"),
                                "final_url": page.get("final_url"),
                                "deterministic_evidence": True,
                            },
                        ),
                        explanation="URL was reached, but direct reading was blocked by anti-bot verification.",
                        metadata={
                            "deterministic_evidence": True,
                            "blocked_by_antibot": True,
                        },
                    )
                )

        return evidence_set

    def _read_page_url(
        self,
        page: dict[str, Any],
    ) -> str | None:
        for key in ["url", "final_url"]:
            value = page.get(key)

            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value.strip()

        return None

    def _read_page_title(
        self,
        page: dict[str, Any],
    ) -> str | None:
        value = page.get("title")

        if isinstance(value, str) and value.strip():
            return value.strip()

        return None

    def _read_page_raw_text(
        self,
        page: dict[str, Any],
    ) -> str | None:
        parts: list[str] = []

        for key in ["title", "description", "text_preview", "error"]:
            value = page.get(key)

            if isinstance(value, str) and value.strip():
                parts.append(value.strip())

        if not parts:
            return None

        return " ".join(parts)[:1000]

    def _guess_url_evidence_field(
        self,
        url: str,
    ) -> str:
        normalized_url = url.lower()

        ticket_markers = [
            "kassir.ru",
            "redkassa.ru",
            "ticketland.ru",
            "qtickets",
            "ticketscloud",
            "radario",
            "afisha.yandex",
            "iframeab",
        ]

        if any(marker in normalized_url for marker in ticket_markers):
            return "ticket_link"

        return "official_source"

    def _normalize_single_evidence_by_urls(
        self,
        evidence: AgentEvidence,
        blocked_urls: set[str],
        readable_pages: dict[str, dict[str, Any]],
    ) -> None:
        if evidence.source is None:
            return

        source_type = evidence.source.source_type.strip().lower()
        source_url = self._normalize_url_for_compare(evidence.source.url)

        if not source_url:
            if source_type in {"url_read", "url_parser"}:
                self._downgrade_evidence(
                    evidence=evidence,
                    reason="URL-source evidence has no source URL.",
                )
            return

        if source_url in blocked_urls:
            self._downgrade_evidence(
                evidence=evidence,
                reason="Source URL was blocked by anti-bot verification.",
            )
            evidence.source.metadata["blocked_by_antibot"] = True
            return

        if source_type not in {"url_read", "url_parser"}:
            return

        page = readable_pages.get(source_url)

        if page is None:
            self._downgrade_evidence(
                evidence=evidence,
                reason="Source URL was not successfully read by url_read.",
            )
            return

        evidence.source.source_type = "url_read"
        evidence.source.metadata["url_read_ok"] = True
        evidence.source.metadata["status_code"] = page.get("status_code")
        evidence.source.metadata["final_url"] = page.get("final_url")

        if not self._page_supports_evidence(
            page=page,
            evidence=evidence,
        ):
            self._downgrade_evidence(
                evidence=evidence,
                reason="Readable URL page does not directly contain the evidence value.",
            )

    def _page_supports_evidence(
        self,
        page: dict[str, Any],
        evidence: AgentEvidence,
    ) -> bool:
        source_url = self._normalize_url_for_compare(
            evidence.source.url
            if evidence.source is not None
            else None
        )

        value_text = str(evidence.value)
        raw_text = evidence.source.raw_text if evidence.source is not None else None

        if self._looks_like_url(value_text):
            return self._normalize_url_for_compare(value_text) == source_url

        haystack = self._normalize_text_for_compare(
            " ".join(
                str(part or "")
                for part in [
                    page.get("url"),
                    page.get("final_url"),
                    page.get("title"),
                    page.get("description"),
                    page.get("text_preview"),
                ]
            )
        )

        candidates = [
            value_text,
            raw_text or "",
        ]

        for candidate in candidates:
            normalized_candidate = self._normalize_text_for_compare(candidate)

            if not normalized_candidate:
                continue

            if normalized_candidate in haystack:
                return True

            important_tokens = [
                token
                for token in normalized_candidate.split()
                if len(token) >= 4
            ]

            if important_tokens and all(
                token in haystack
                for token in important_tokens[:4]
            ):
                return True

        return False

    def _build_evidence(
        self,
        item: dict[str, Any],
    ) -> AgentEvidence | None:
        field = self._read_string(item, "field")
        value = item.get("value")

        if not field or value is None:
            return None

        source_type = self._read_string(item, "source_type") or "other"
        source_url = self._read_optional_string(item, "source_url")
        raw_text = self._read_optional_string(item, "raw_text")
        explanation = self._read_optional_string(item, "explanation")

        confidence = self._read_confidence(item)
        status = self._read_status(item)

        confidence, status = self._normalize_extracted_trust(
            source_type=source_type,
            source_url=source_url,
            raw_text=raw_text,
            explanation=explanation,
            confidence=confidence,
            status=status,
        )

        source = EvidenceSource(
            source_type=source_type,
            title=self._read_optional_string(item, "source_title"),
            url=source_url,
            raw_text=raw_text,
        )

        return AgentEvidence(
            field=field,
            value=value,
            confidence=confidence,
            status=status,
            source=source,
            explanation=explanation,
        )

    def _normalize_extracted_trust(
        self,
        source_type: str,
        source_url: str | None,
        raw_text: str | None,
        explanation: str | None,
        confidence: EvidenceConfidence,
        status: EvidenceStatus,
    ) -> tuple[EvidenceConfidence, EvidenceStatus]:
        normalized_source_type = source_type.strip().lower()

        weak_markers = [
            "уточняется",
            "например",
            "обычно",
            "можно увидеть",
            "после перехода",
            "предполож",
            "примерн",
            "может",
            "как правило",
        ]

        text_for_check = " ".join(
            part
            for part in [
                raw_text or "",
                explanation or "",
            ]
            if part
        ).lower()

        if any(marker in text_for_check for marker in weak_markers):
            return EvidenceConfidence.LOW, EvidenceStatus.UNVERIFIED

        if status in {EvidenceStatus.CONFLICTED, EvidenceStatus.REJECTED}:
            return confidence, status

        if normalized_source_type == "search":
            if confidence == EvidenceConfidence.HIGH:
                confidence = EvidenceConfidence.MEDIUM

            return confidence, EvidenceStatus.UNVERIFIED

        trusted_verified_sources = {
            "db",
            "url_read",
            "url_parser",
            "manual_confirmed",
        }

        if (
            status == EvidenceStatus.VERIFIED
            and normalized_source_type not in trusted_verified_sources
            and not source_url
        ):
            return EvidenceConfidence.MEDIUM, EvidenceStatus.UNVERIFIED

        return confidence, status

    def _downgrade_evidence(
        self,
        evidence: AgentEvidence,
        reason: str,
    ) -> None:
        evidence.status = EvidenceStatus.UNVERIFIED

        if evidence.confidence == EvidenceConfidence.HIGH:
            evidence.confidence = EvidenceConfidence.MEDIUM

        if evidence.explanation:
            evidence.explanation = f"{evidence.explanation} {reason}"
        else:
            evidence.explanation = reason

        evidence.metadata["trust_downgraded"] = True
        evidence.metadata["trust_downgrade_reason"] = reason

    def _normalize_url_for_compare(
        self,
        value: Any,
    ) -> str:
        if not isinstance(value, str):
            return ""

        text = value.strip()

        if not text:
            return ""

        parsed = urllib.parse.urlparse(text)

        if not parsed.scheme:
            text = f"https://{text}"
            parsed = urllib.parse.urlparse(text)

        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")

        return urllib.parse.urlunparse(
            (
                parsed.scheme.lower(),
                netloc,
                path,
                "",
                "",
                "",
            )
        )

    def _normalize_text_for_compare(
        self,
        value: str,
    ) -> str:
        text = value.lower()
        text = text.replace("ё", "е")
        text = re.sub(
            r"[^\wа-яА-Я0-9:/.-]+",
            " ",
            text,
            flags=re.UNICODE,
        )
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _looks_like_url(
        self,
        value: str,
    ) -> bool:
        return value.startswith("http://") or value.startswith("https://")

    def _read_confidence(
        self,
        item: dict[str, Any],
    ) -> EvidenceConfidence:
        value = self._read_string(item, "confidence")

        try:
            return EvidenceConfidence(value)
        except ValueError:
            return EvidenceConfidence.LOW

    def _read_status(
        self,
        item: dict[str, Any],
    ) -> EvidenceStatus:
        value = self._read_string(item, "status")

        try:
            return EvidenceStatus(value)
        except ValueError:
            return EvidenceStatus.UNVERIFIED

    def _read_string(
        self,
        item: dict[str, Any],
        key: str,
    ) -> str:
        value = item.get(key)

        if not isinstance(value, str):
            return ""

        return value.strip()

    def _read_optional_string(
        self,
        item: dict[str, Any],
        key: str,
    ) -> str | None:
        value = self._read_string(item, key)

        return value or None
    



