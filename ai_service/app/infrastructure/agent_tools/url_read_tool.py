import asyncio
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from html.parser import HTMLParser
from typing import Any

from app.application.agent_core.tool_enums import (
    AgentToolCategory,
    AgentToolCostLevel,
    AgentToolTrustLevel,
)
from app.application.agent_core.tools import (
    AgentToolInput,
    AgentToolOutput,
    AgentToolSpec,
)


class _SimpleHtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()

        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.meta_description: str | None = None

        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()

        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return

        if tag == "title":
            self._in_title = True
            return

        if tag == "meta":
            self._read_meta(attrs)

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        tag = tag.lower()

        if tag in {"script", "style", "noscript", "svg"}:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

        if tag == "title":
            self._in_title = False

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._skip_depth > 0:
            return

        text = data.strip()

        if not text:
            return

        if self._in_title:
            self.title_parts.append(text)
            return

        self.text_parts.append(text)

    def title(
        self,
    ) -> str | None:
        title = self._clean_text(" ".join(self.title_parts))

        if not title:
            return None

        return title

    def text_preview(
        self,
        limit: int,
    ) -> str:
        text = self._clean_text(" ".join(self.text_parts))

        if len(text) <= limit:
            return text

        return text[:limit].rstrip() + "..."

    def _read_meta(
        self,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attrs_dict = {
            key.lower(): value or ""
            for key, value in attrs
        }

        name = attrs_dict.get("name", "").lower()
        property_name = attrs_dict.get("property", "").lower()

        if name != "description" and property_name != "og:description":
            return

        content = attrs_dict.get("content", "").strip()

        if content:
            self.meta_description = unescape(content)

    def _clean_text(
        self,
        value: str,
    ) -> str:
        value = unescape(value)
        value = re.sub(r"\s+", " ", value)

        return value.strip()


class UrlReadAgentTool:
    def __init__(
        self,
        timeout_seconds: float = 20.0,
        text_preview_limit: int = 5000,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._text_preview_limit = text_preview_limit

    @property
    def spec(
        self,
    ) -> AgentToolSpec:
        return AgentToolSpec(
            name="url_read",
            description=(
                "Открывает URL, получает финальный адрес, HTTP-статус, title, "
                "description и короткий текст страницы. Используй этот инструмент "
                "для проверки конкретных ссылок, найденных во входном тексте, "
                "кнопках, QR-кодах или через поиск."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                        "description": "Список URL для проверки.",
                    },
                },
                "required": ["urls"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "pages": {
                        "type": "array",
                    },
                },
            },
            category=AgentToolCategory.VERIFICATION,
            capabilities=[
                "verify_url",
                "read_page",
                "expand_url",
                "extract_page_title",
                "extract_page_description",
                "extract_page_text",
                "detect_antibot",
                "verify_source_page",
            ],
            produces_evidence=True,
            trust_level=AgentToolTrustLevel.HIGH,
            cost_level=AgentToolCostLevel.LOW,
            can_run_automatically=True,
            can_be_called_by_agent=True,
            timeout_seconds=self._timeout_seconds,
        )

    async def run(
        self,
        tool_input: AgentToolInput,
    ) -> AgentToolOutput:
        urls = self._read_urls(tool_input.arguments)

        if not urls:
            return AgentToolOutput(
                tool_name=self.spec.name,
                ok=False,
                error="Argument 'urls' is required",
            )

        pages = []

        for url in urls:
            page = await asyncio.to_thread(
                self._read_url_sync,
                url,
            )
            pages.append(page)

        return AgentToolOutput(
            tool_name=self.spec.name,
            ok=True,
            data={
                "pages": pages,
            },
            metadata={
                "url_count": len(urls),
                "successful_count": self._count_successful_pages(pages),
                "blocked_by_antibot_count": self._count_blocked_pages(pages),
            },
        )

    def _read_urls(
        self,
        arguments: dict[str, Any],
    ) -> list[str]:
        value = arguments.get("urls")

        if isinstance(value, str):
            raw_urls = [value]
        elif isinstance(value, list):
            raw_urls = [
                item
                for item in value
                if isinstance(item, str)
            ]
        else:
            raw_urls = []

        result = []

        for url in raw_urls:
            normalized_url = self._normalize_url(url)

            if normalized_url is not None:
                result.append(normalized_url)

        return result

    def _normalize_url(
        self,
        url: str,
    ) -> str | None:
        value = url.strip()

        if not value:
            return None

        parsed = urllib.parse.urlparse(value)

        if not parsed.scheme:
            value = f"https://{value}"
            parsed = urllib.parse.urlparse(value)

        if parsed.scheme not in {"http", "https"}:
            return None

        if not parsed.netloc:
            return None

        return value

    def _read_url_sync(
        self,
        url: str,
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            url=url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,*/*;q=0.8"
                ),
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                raw = response.read(2_000_000)
                final_url = response.geturl()
                status_code = getattr(response, "status", None)
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            return self._build_failed_page(
                url=url,
                status_code=exc.code,
                final_url=exc.url,
                error=f"HTTPError: {exc}",
            )
        except Exception as exc:
            return self._build_failed_page(
                url=url,
                status_code=None,
                final_url=None,
                error=f"{type(exc).__name__}: {exc}",
            )

        encoding = self._detect_encoding(content_type)
        html = raw.decode(encoding, errors="replace")

        extractor = _SimpleHtmlTextExtractor()
        extractor.feed(html)

        title = extractor.title()
        description = extractor.meta_description
        text_preview = extractor.text_preview(self._text_preview_limit)

        blocked_by_antibot = self._is_antibot_page(
            final_url=final_url,
            title=title,
            text_preview=text_preview,
        )

        if blocked_by_antibot:
            return {
                "url": url,
                "ok": False,
                "blocked_by_antibot": True,
                "status_code": status_code,
                "final_url": final_url,
                "content_type": content_type,
                "title": title,
                "description": description,
                "text_preview": text_preview,
                "error": "Anti-bot verification page",
            }

        return {
            "url": url,
            "ok": True,
            "blocked_by_antibot": False,
            "status_code": status_code,
            "final_url": final_url,
            "content_type": content_type,
            "title": title,
            "description": description,
            "text_preview": text_preview,
            "error": None,
        }

    def _build_failed_page(
        self,
        url: str,
        status_code: int | None,
        final_url: str | None,
        error: str,
    ) -> dict[str, Any]:
        return {
            "url": url,
            "ok": False,
            "blocked_by_antibot": False,
            "status_code": status_code,
            "final_url": final_url,
            "content_type": None,
            "title": None,
            "description": None,
            "text_preview": "",
            "error": error,
        }

    def _is_antibot_page(
        self,
        final_url: str | None,
        title: str | None,
        text_preview: str,
    ) -> bool:
        final_url_text = (final_url or "").lower()
        title_text = (title or "").lower()
        body_text = text_preview.lower()

        if "fg.kassir.ru" in final_url_text:
            return True

        markers = [
            "требуется действие",
            "необходимо подтверждение",
            "важно знать, что вы не робот",
            "пройдите проверку",
            "captcha",
            "cloudflare",
            "are you human",
            "verify you are human",
        ]

        haystack = " ".join(
            [
                title_text,
                body_text,
            ]
        )

        return any(marker in haystack for marker in markers)

    def _detect_encoding(
        self,
        content_type: str,
    ) -> str:
        match = re.search(
            r"charset=([^;\s]+)",
            content_type,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1).strip()

        return "utf-8"

    def _count_successful_pages(
        self,
        pages: list[dict[str, Any]],
    ) -> int:
        return sum(
            1
            for page in pages
            if page.get("ok") is True
        )

    def _count_blocked_pages(
        self,
        pages: list[dict[str, Any]],
    ) -> int:
        return sum(
            1
            for page in pages
            if page.get("blocked_by_antibot") is True
        )
        



