from __future__ import annotations

import html
import re


A_TAG_RE = re.compile(
    r'<a\s+[^>]*href=[\'"](?P<href>[^\'"]+)[\'"][^>]*>(?P<text>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
P_CLOSE_RE = re.compile(r"</p\s*>", re.IGNORECASE)
DIV_CLOSE_RE = re.compile(r"</div\s*>", re.IGNORECASE)


def html_to_text(value: str | None) -> str:
    if not value:
        return ""

    text = value

    text = BR_RE.sub("\n", text)
    text = P_CLOSE_RE.sub("\n", text)
    text = DIV_CLOSE_RE.sub("\n", text)

    def replace_a_tag(match: re.Match[str]) -> str:
        inner_text = TAG_RE.sub("", match.group("text")).strip()
        href = html.unescape(match.group("href")).strip()

        if inner_text:
            return f"{inner_text} {href}"

        return href

    text = A_TAG_RE.sub(replace_a_tag, text)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)

    return text.strip()

