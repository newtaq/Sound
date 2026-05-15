from __future__ import annotations

from app.services.poster_ocr.dictionaries.runtime_dictionary import RuntimeDictionary
from app.services.poster_ocr.normalize.merged_token_normalizer import normalize_merged_token
from app.services.poster_ocr.normalize.phrase_matcher import match_phrase


def normalize_merged_line(
    text: str,
    dictionary: RuntimeDictionary | None = None,
) -> str:
    value = text.strip()
    if not value:
        return ""

    parts = [normalize_merged_token(part) for part in value.split()]
    parts = [part for part in parts if part]

    merged_text = " ".join(parts)

    if dictionary is None:
        return merged_text

    return match_phrase(
        merged_text,
        dictionary=dictionary,
        threshold=0.72,
    )
    