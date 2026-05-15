from __future__ import annotations

from app.services.poster_ocr.backends.ocr_space_backend import OCRSpaceBackend
from app.services.poster_ocr.backends.paddle_ocr_backend import PaddleOCRBackend
from app.services.poster_ocr.config import PosterOCRConfig
from app.services.poster_ocr.protocols import OCRBackend


def build_default_ocr_backends(config: PosterOCRConfig) -> list[OCRBackend]:
    backends: list[OCRBackend] = []

    if config.enable_ocr_space and config.ocr_space.enabled:
        backends.append(OCRSpaceBackend(config=config.ocr_space))

    if config.enable_paddle and config.paddle.enabled:
        backends.append(PaddleOCRBackend(config=config.paddle))

    return backends
