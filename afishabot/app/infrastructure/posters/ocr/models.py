from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


BBox = tuple[int, int, int, int]


@dataclass(slots=True)
class PosterImage:
    data: bytes
    filename: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass(slots=True)
class EntityCandidate:
    entity_type: str
    name: str
    confidence: float = 0.0
    entity_id: int | None = None
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = ""


@dataclass(slots=True)
class PosterOCRContext:
    description_text: str | None = None
    entity_candidates: list[EntityCandidate] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PosterOCRRequest:
    image: PosterImage
    context: PosterOCRContext = field(default_factory=PosterOCRContext)
    use_external_ocr: bool = True
    deep_mode: bool = True
    debug: bool = False


@dataclass(slots=True)
class OCRCharCandidate:
    value: str
    confidence: float


@dataclass(slots=True)
class OCRChar:
    value: str
    confidence: float
    bbox: BBox
    candidates: list[OCRCharCandidate] = field(default_factory=list)
    source: str = ""


@dataclass(slots=True)
class OCRWordCandidate:
    text: str
    confidence: float
    language: str = "unknown"


@dataclass(slots=True)
class OCRWord:
    text: str
    confidence: float
    bbox: BBox
    chars: list[OCRChar] = field(default_factory=list)
    candidates: list[OCRWordCandidate] = field(default_factory=list)
    language: str = "unknown"
    source: str = ""


@dataclass(slots=True)
class OCRLineCandidate:
    text: str
    confidence: float


@dataclass(slots=True)
class OCRLine:
    text: str
    confidence: float
    bbox: BBox
    words: list[OCRWord] = field(default_factory=list)
    candidates: list[OCRLineCandidate] = field(default_factory=list)
    source: str = ""


@dataclass(slots=True)
class OCRBlock:
    text: str
    confidence: float
    bbox: BBox
    lines: list[OCRLine] = field(default_factory=list)
    block_type: str = "unknown"
    reading_order: int = 0
    source: str = ""


@dataclass(slots=True)
class OCRBackendRequest:
    image: PosterImage
    context: PosterOCRContext = field(default_factory=PosterOCRContext)
    block: OCRBlock | None = None
    debug: bool = False


@dataclass(slots=True)
class OCRBackendResult:
    backend_name: str
    raw_text: str
    confidence: float
    blocks: list[OCRBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PosterEntityHint:
    entity_type: str
    value: str
    confidence: float
    source: str = ""
    entity_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PosterImageFingerprint:
    sha256: str
    phash: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass(slots=True)
class PosterDebugData:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PosterOCRResult:
    raw_text: str
    normalized_text: str
    confidence: float
    blocks: list[OCRBlock] = field(default_factory=list)
    entity_hints: list[PosterEntityHint] = field(default_factory=list)
    fingerprint: PosterImageFingerprint | None = None
    debug: PosterDebugData = field(default_factory=PosterDebugData)
    
