from __future__ import annotations

import re

from app.infrastructure.posters.ocr.models import OCRBlock


_MIN_CONFIDENCE = 0.30
_MIN_TEXT_LENGTH = 2


def accept_block(block: OCRBlock) -> bool:
    text = block.text.strip()

    if not text:
        return False

    if len(text) < _MIN_TEXT_LENGTH:
        return False

    if block.confidence < _MIN_CONFIDENCE:
        return False

    if _is_only_punctuation(text):
        return False

    if _is_noise_token(text):
        return False

    return True


def _is_only_punctuation(text: str) -> bool:
    return bool(re.fullmatch(r"[^\w]+", text))


def _is_noise_token(text: str) -> bool:
    if re.fullmatch(r"[A-Z]{1,2}", text):
        return True

    if re.fullmatch(r"[0-9]{1,2}\.", text):
        return True

    if re.fullmatch(r"[Xx]{1,3}", text):
        return True

    return False

