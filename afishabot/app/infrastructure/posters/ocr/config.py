from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _get_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default))


def _normalize_backend_execution_mode(value: str | None) -> str:
    if not value:
        return "run_all"

    normalized = value.strip().lower()
    if normalized in {"run_all", "first_success"}:
        return normalized

    return "run_all"


@dataclass(slots=True)
class OCRSpaceConfig:
    enabled: bool
    api_key: str
    endpoint: str
    timeout_seconds: float
    language: str
    overlay_required: bool
    scale: bool
    ocr_engine: int
    detect_orientation: bool


@dataclass(slots=True)
class PaddleOCRConfig:
    enabled: bool
    use_gpu: bool
    timeout_seconds: float
    det_model_dir: Path
    cls_model_dir: Path
    rec_cyrillic_model_dir: Path
    rec_latin_model_dir: Path
    rec_english_model_dir: Path
    enable_textline_orientation: bool
    enable_doc_orientation: bool
    enable_rectify: bool


@dataclass(slots=True)
class PosterOCRConfig:
    pipeline_version: str
    backend_execution_mode: str
    enable_ocr_space: bool
    enable_paddle: bool
    ocr_space: OCRSpaceConfig
    paddle: PaddleOCRConfig


def build_default_ocr_space_config(
    *,
    enabled: bool = True,
    api_key: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: float | None = None,
    language: str | None = None,
    overlay_required: bool | None = None,
    scale: bool | None = None,
    ocr_engine: int | None = None,
    detect_orientation: bool | None = None,
) -> OCRSpaceConfig:
    return OCRSpaceConfig(
        enabled=enabled,
        api_key=api_key if api_key is not None else os.getenv("OCR_SPACE_API_KEY", "helloworld"),
        endpoint=endpoint if endpoint is not None else os.getenv(
            "OCR_SPACE_ENDPOINT",
            "https://api.ocr.space/parse/image",
        ),
        timeout_seconds=timeout_seconds if timeout_seconds is not None else _get_float(
            "OCR_SPACE_TIMEOUT_SECONDS",
            60.0,
        ),
        language=language if language is not None else os.getenv("OCR_SPACE_LANGUAGE", "eng"),
        overlay_required=overlay_required if overlay_required is not None else _get_bool(
            "OCR_SPACE_OVERLAY_REQUIRED",
            True,
        ),
        scale=scale if scale is not None else _get_bool("OCR_SPACE_SCALE", True),
        ocr_engine=ocr_engine if ocr_engine is not None else _get_int(
            "OCR_SPACE_OCR_ENGINE",
            2,
        ),
        detect_orientation=detect_orientation if detect_orientation is not None else _get_bool(
            "OCR_SPACE_DETECT_ORIENTATION",
            False,
        ),
    )


def build_default_paddle_config(
    *,
    enabled: bool = True,
    use_gpu: bool | None = None,
    timeout_seconds: float | None = None,
    det_model_dir: str | Path | None = None,
    cls_model_dir: str | Path | None = None,
    rec_cyrillic_model_dir: str | Path | None = None,
    rec_latin_model_dir: str | Path | None = None,
    rec_english_model_dir: str | Path | None = None,
    enable_textline_orientation: bool | None = None,
    enable_doc_orientation: bool | None = None,
    enable_rectify: bool | None = None,
) -> PaddleOCRConfig:
    return PaddleOCRConfig(
        enabled=enabled,
        use_gpu=use_gpu if use_gpu is not None else _get_bool("PADDLE_USE_GPU", False),
        timeout_seconds=timeout_seconds if timeout_seconds is not None else _get_float(
            "PADDLE_TIMEOUT_SECONDS",
            120.0,
        ),
        det_model_dir=Path(det_model_dir) if det_model_dir is not None else _get_path(
            "PADDLE_DET_MODEL_DIR",
            "models/paddle/det/PP-OCRv5_mobile_det",
        ),
        cls_model_dir=Path(cls_model_dir) if cls_model_dir is not None else _get_path(
            "PADDLE_CLS_MODEL_DIR",
            "models/paddle/cls/PP-LCNet_x0_25_textline_ori",
        ),
        rec_cyrillic_model_dir=Path(rec_cyrillic_model_dir) if rec_cyrillic_model_dir is not None else _get_path(
            "PADDLE_REC_CYRILLIC_MODEL_DIR",
            "models/paddle/rec/cyrillic_PP-OCRv5_mobile_rec",
        ),
        rec_latin_model_dir=Path(rec_latin_model_dir) if rec_latin_model_dir is not None else _get_path(
            "PADDLE_REC_LATIN_MODEL_DIR",
            "models/paddle/rec/latin_PP-OCRv5_mobile_rec",
        ),
        rec_english_model_dir=Path(rec_english_model_dir) if rec_english_model_dir is not None else _get_path(
            "PADDLE_REC_ENGLISH_MODEL_DIR",
            "models/paddle/rec/en_PP-OCRv5_mobile_rec",
        ),
        enable_textline_orientation=enable_textline_orientation
        if enable_textline_orientation is not None
        else _get_bool("PADDLE_ENABLE_TEXTLINE_ORIENTATION", True),
        enable_doc_orientation=enable_doc_orientation
        if enable_doc_orientation is not None
        else _get_bool("PADDLE_ENABLE_DOC_ORIENTATION", False),
        enable_rectify=enable_rectify
        if enable_rectify is not None
        else _get_bool("PADDLE_ENABLE_RECTIFY", False),
    )


def build_poster_ocr_config() -> PosterOCRConfig:
    enable_ocr_space = _get_bool("OCR_ENABLE_OCR_SPACE", True)
    enable_paddle = _get_bool("OCR_ENABLE_PADDLE", True)

    ocr_space = build_default_ocr_space_config(
        enabled=_get_bool("OCR_SPACE_ENABLED", enable_ocr_space),
    )
    paddle = build_default_paddle_config(
        enabled=_get_bool("PADDLE_ENABLED", enable_paddle),
    )

    return PosterOCRConfig(
        pipeline_version=os.getenv("OCR_PIPELINE_VERSION", "v1"),
        backend_execution_mode=_normalize_backend_execution_mode(
            os.getenv("OCR_BACKEND_EXECUTION_MODE", "run_all")
        ),
        enable_ocr_space=enable_ocr_space,
        enable_paddle=enable_paddle,
        ocr_space=ocr_space,
        paddle=paddle,
    )


def build_paddle_only_config(
    *,
    pipeline_version: str = "v1",
    backend_execution_mode: str = "first_success",
    paddle: PaddleOCRConfig | None = None,
) -> PosterOCRConfig:
    paddle_config = paddle or build_default_paddle_config(enabled=True)

    return PosterOCRConfig(
        pipeline_version=pipeline_version,
        backend_execution_mode=_normalize_backend_execution_mode(backend_execution_mode),
        enable_ocr_space=False,
        enable_paddle=True,
        ocr_space=build_default_ocr_space_config(enabled=False),
        paddle=PaddleOCRConfig(
            enabled=True,
            use_gpu=paddle_config.use_gpu,
            timeout_seconds=paddle_config.timeout_seconds,
            det_model_dir=paddle_config.det_model_dir,
            cls_model_dir=paddle_config.cls_model_dir,
            rec_cyrillic_model_dir=paddle_config.rec_cyrillic_model_dir,
            rec_latin_model_dir=paddle_config.rec_latin_model_dir,
            rec_english_model_dir=paddle_config.rec_english_model_dir,
            enable_textline_orientation=paddle_config.enable_textline_orientation,
            enable_doc_orientation=paddle_config.enable_doc_orientation,
            enable_rectify=paddle_config.enable_rectify,
        ),
    )


def build_ocr_space_only_config(
    *,
    pipeline_version: str = "v1",
    backend_execution_mode: str = "first_success",
    ocr_space: OCRSpaceConfig | None = None,
) -> PosterOCRConfig:
    ocr_space_config = ocr_space or build_default_ocr_space_config(enabled=True)

    return PosterOCRConfig(
        pipeline_version=pipeline_version,
        backend_execution_mode=_normalize_backend_execution_mode(backend_execution_mode),
        enable_ocr_space=True,
        enable_paddle=False,
        ocr_space=OCRSpaceConfig(
            enabled=True,
            api_key=ocr_space_config.api_key,
            endpoint=ocr_space_config.endpoint,
            timeout_seconds=ocr_space_config.timeout_seconds,
            language=ocr_space_config.language,
            overlay_required=ocr_space_config.overlay_required,
            scale=ocr_space_config.scale,
            ocr_engine=ocr_space_config.ocr_engine,
            detect_orientation=ocr_space_config.detect_orientation,
        ),
        paddle=build_default_paddle_config(enabled=False),
    )


def build_dual_backend_config(
    *,
    pipeline_version: str = "v1",
    backend_execution_mode: str = "run_all",
    ocr_space: OCRSpaceConfig | None = None,
    paddle: PaddleOCRConfig | None = None,
) -> PosterOCRConfig:
    ocr_space_config = ocr_space or build_default_ocr_space_config(enabled=True)
    paddle_config = paddle or build_default_paddle_config(enabled=True)

    return PosterOCRConfig(
        pipeline_version=pipeline_version,
        backend_execution_mode=_normalize_backend_execution_mode(backend_execution_mode),
        enable_ocr_space=True,
        enable_paddle=True,
        ocr_space=OCRSpaceConfig(
            enabled=True,
            api_key=ocr_space_config.api_key,
            endpoint=ocr_space_config.endpoint,
            timeout_seconds=ocr_space_config.timeout_seconds,
            language=ocr_space_config.language,
            overlay_required=ocr_space_config.overlay_required,
            scale=ocr_space_config.scale,
            ocr_engine=ocr_space_config.ocr_engine,
            detect_orientation=ocr_space_config.detect_orientation,
        ),
        paddle=PaddleOCRConfig(
            enabled=True,
            use_gpu=paddle_config.use_gpu,
            timeout_seconds=paddle_config.timeout_seconds,
            det_model_dir=paddle_config.det_model_dir,
            cls_model_dir=paddle_config.cls_model_dir,
            rec_cyrillic_model_dir=paddle_config.rec_cyrillic_model_dir,
            rec_latin_model_dir=paddle_config.rec_latin_model_dir,
            rec_english_model_dir=paddle_config.rec_english_model_dir,
            enable_textline_orientation=paddle_config.enable_textline_orientation,
            enable_doc_orientation=paddle_config.enable_doc_orientation,
            enable_rectify=paddle_config.enable_rectify,
        ),
    )
    
