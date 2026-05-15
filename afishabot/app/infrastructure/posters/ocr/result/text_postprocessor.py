from __future__ import annotations

import re

SPACE_FIX_RE = re.compile(r"\s{2,}")
CHAR_FIX_RE = re.compile(r"[^\w\s\.\:\+\-]")


class PosterTextPostProcessor:
    def process(self, text: str) -> str:
        if not text:
            return ""

        text = self._normalize_whitespace(text)
        text = self._remove_noise(text)
        text = self._normalize_case(text)

        return text.strip()

    def _normalize_whitespace(self, text: str) -> str:
        text = text.replace("\r", "")
        text = SPACE_FIX_RE.sub(" ", text)
        return text

    def _remove_noise(self, text: str) -> str:
        return CHAR_FIX_RE.sub("", text)

    def _normalize_case(self, text: str) -> str:
        return text
    
