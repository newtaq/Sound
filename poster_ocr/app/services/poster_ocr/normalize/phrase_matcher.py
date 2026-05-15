from __future__ import annotations

from difflib import SequenceMatcher

from app.services.poster_ocr.dictionaries.runtime_dictionary import RuntimeDictionary


CANONICAL_CHAR_MAP = {
    "A": "A",
    "А": "A",
    "a": "a",
    "а": "a",
    "B": "B",
    "В": "B",
    "Б": "B",
    "C": "C",
    "С": "C",
    "c": "c",
    "с": "c",
    "E": "E",
    "Е": "E",
    "e": "e",
    "е": "e",
    "H": "H",
    "Н": "H",
    "K": "K",
    "К": "K",
    "M": "M",
    "М": "M",
    "O": "O",
    "О": "O",
    "o": "o",
    "о": "o",
    "P": "P",
    "Р": "P",
    "p": "p",
    "р": "p",
    "T": "T",
    "Т": "T",
    "X": "X",
    "Х": "X",
    "x": "x",
    "х": "x",
    "Y": "Y",
    "У": "Y",
    "y": "y",
    "у": "y",
    "I": "I",
    "І": "I",
    "l": "l",
    "1": "1",
}


def match_phrase(
    value: str,
    dictionary: RuntimeDictionary,
    threshold: float = 0.72,
) -> str:
    text = value.strip()
    if not text:
        return ""

    best_value = text
    best_score = threshold

    normalized_input = _normalize(text)
    canonical_input = _canonicalize(normalized_input)

    for candidate in dictionary.get_all():
        normalized_candidate = _normalize(candidate)
        canonical_candidate = _canonicalize(normalized_candidate)

        direct_score = SequenceMatcher(
            None,
            normalized_input,
            normalized_candidate,
        ).ratio()

        canonical_score = SequenceMatcher(
            None,
            canonical_input,
            canonical_candidate,
        ).ratio()

        score = max(direct_score, canonical_score)

        if score > best_score:
            best_score = score
            best_value = candidate

    return best_value


def _normalize(value: str) -> str:
    return "".join(value.lower().split())


def _canonicalize(value: str) -> str:
    return "".join(CANONICAL_CHAR_MAP.get(char, char) for char in value)
