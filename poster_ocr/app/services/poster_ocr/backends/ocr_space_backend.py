from __future__ import annotations

import httpx

from app.services.poster_ocr.backends.base import BaseOCRBackend
from app.services.poster_ocr.config import OCRSpaceConfig, build_poster_ocr_config
from app.services.poster_ocr.language.script_detector import detect_word_script
from app.services.poster_ocr.models import (
    BBox,
    OCRBackendRequest,
    OCRBackendResult,
    OCRBlock,
    OCRLine,
    OCRWord,
)


class OCRSpaceBackend(BaseOCRBackend):
    name = "ocr_space"

    def __init__(self, config: OCRSpaceConfig | None = None) -> None:
        self._config = config or build_poster_ocr_config().ocr_space

    async def recognize(self, request: OCRBackendRequest) -> OCRBackendResult:
        if not self._config.enabled:
            return OCRBackendResult(
                backend_name=self.name,
                raw_text="",
                confidence=0.0,
                blocks=[],
                metadata={"disabled": True},
            )

        if not self._config.api_key:
            return OCRBackendResult(
                backend_name=self.name,
                raw_text="",
                confidence=0.0,
                blocks=[],
                metadata={"error": "missing_api_key"},
            )

        files = {
            "file": (
                request.image.filename or "poster.jpg",
                request.image.data,
                request.image.mime_type or "application/octet-stream",
            )
        }

        data = {
            "apikey": self._config.api_key,
            "language": self._config.language,
            "isOverlayRequired": self._bool_to_str(self._config.overlay_required),
            "scale": self._bool_to_str(self._config.scale),
            "detectOrientation": self._bool_to_str(self._config.detect_orientation),
            "OCREngine": str(self._config.ocr_engine),
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._config.timeout_seconds
            ) as client:
                response = await client.post(
                    self._config.endpoint,
                    data=data,
                    files=files,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            response_text = ""
            try:
                response_text = exc.response.text[:1000]
            except Exception:
                response_text = ""

            return OCRBackendResult(
                backend_name=self.name,
                raw_text="",
                confidence=0.0,
                blocks=[],
                metadata={
                    "error": "http_status_error",
                    "error_type": type(exc).__name__,
                    "status_code": exc.response.status_code,
                    "response_text": response_text,
                },
            )
        except httpx.RequestError as exc:
            return OCRBackendResult(
                backend_name=self.name,
                raw_text="",
                confidence=0.0,
                blocks=[],
                metadata={
                    "error": "request_error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
            )
        except Exception as exc:
            return OCRBackendResult(
                backend_name=self.name,
                raw_text="",
                confidence=0.0,
                blocks=[],
                metadata={
                    "error": "unexpected_error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
            )

        try:
            payload = response.json()
        except ValueError:
            return OCRBackendResult(
                backend_name=self.name,
                raw_text="",
                confidence=0.0,
                blocks=[],
                metadata={"error": "invalid_json"},
            )

        lines = self._extract_lines(payload)
        blocks = self._build_blocks(lines)
        raw_text = "\n".join(line.text for line in lines if line.text.strip())

        return OCRBackendResult(
            backend_name=self.name,
            raw_text=raw_text,
            confidence=self._estimate_confidence(lines),
            blocks=blocks,
            metadata={"payload": payload},
        )

    def _extract_lines(self, payload: dict) -> list[OCRLine]:
        parsed_results = payload.get("ParsedResults") or []
        result_lines: list[OCRLine] = []

        for parsed_result in parsed_results:
            text_overlay = parsed_result.get("TextOverlay") or {}
            lines = text_overlay.get("Lines") or []

            for line_data in lines:
                words = self._extract_words(line_data)
                line_text = self._normalize_spaces(
                    line_data.get("LineText") or " ".join(word.text for word in words)
                )
                line_bbox = self._line_bbox(line_data, words)

                result_lines.append(
                    OCRLine(
                        text=line_text,
                        confidence=self._estimate_line_confidence(words),
                        bbox=line_bbox,
                        words=words,
                        candidates=[],
                        source=self.name,
                    )
                )

        return result_lines

    def _extract_words(self, line_data: dict) -> list[OCRWord]:
        raw_words = line_data.get("Words") or []
        words: list[OCRWord] = []

        for word_data in raw_words:
            text = self._normalize_spaces(word_data.get("WordText") or "")
            if not text:
                continue

            bbox = self._word_bbox(word_data)

            words.append(
                OCRWord(
                    text=text,
                    confidence=0.5,
                    bbox=bbox,
                    chars=[],
                    candidates=[],
                    language=detect_word_script(text),
                    source=self.name,
                )
            )

        return words

    def _build_blocks(self, lines: list[OCRLine]) -> list[OCRBlock]:
        blocks: list[OCRBlock] = []

        for index, line in enumerate(lines):
            blocks.append(
                OCRBlock(
                    text=line.text,
                    confidence=line.confidence,
                    bbox=line.bbox,
                    lines=[line],
                    block_type="unknown",
                    reading_order=index,
                    source=self.name,
                )
            )

        return blocks

    def _line_bbox(self, line_data: dict, words: list[OCRWord]) -> BBox:
        if words:
            left = min(word.bbox[0] for word in words)
            top = min(word.bbox[1] for word in words)
            right = max(word.bbox[0] + word.bbox[2] for word in words)
            bottom = max(word.bbox[1] + word.bbox[3] for word in words)
            return (left, top, right - left, bottom - top)

        left = self._safe_int(line_data.get("MinLeft"))
        top = self._safe_int(line_data.get("MinTop"))
        width = self._safe_int(line_data.get("MaxWidth"))
        height = self._safe_int(line_data.get("MaxHeight"))
        return (left, top, width, height)

    def _word_bbox(self, word_data: dict) -> BBox:
        left = self._safe_int(word_data.get("Left"))
        top = self._safe_int(word_data.get("Top"))
        width = self._safe_int(word_data.get("Width"))
        height = self._safe_int(word_data.get("Height"))
        return (left, top, width, height)

    def _estimate_confidence(self, lines: list[OCRLine]) -> float:
        if not lines:
            return 0.0
        return sum(line.confidence for line in lines) / len(lines)

    def _estimate_line_confidence(self, words: list[OCRWord]) -> float:
        if not words:
            return 0.0
        return sum(word.confidence for word in words) / len(words)

    def _normalize_spaces(self, value: str) -> str:
        return " ".join(value.split())

    def _safe_int(self, value: object) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                return 0
        return 0

    def _bool_to_str(self, value: bool) -> str:
        return "true" if value else "false"
    