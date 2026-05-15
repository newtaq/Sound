from __future__ import annotations

import os
from importlib import metadata as importlib_metadata
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.infrastructure.posters.ocr.config import PaddleOCRConfig, build_poster_ocr_config
from app.infrastructure.posters.ocr.models import (
    OCRBackendRequest,
    OCRBackendResult,
    OCRBlock,
)
from app.infrastructure.posters.ocr.protocols import OCRBackend


class PaddleOCRBackend(OCRBackend):
    name = "paddle_ocr"

    def __init__(self, config: PaddleOCRConfig | None = None) -> None:
        self._config = config or build_poster_ocr_config().paddle
        self._ocr: Any | None = None
        self._init_metadata: dict[str, Any] = {}

    async def recognize(self, request: OCRBackendRequest) -> OCRBackendResult:
        if not self._config.enabled:
            return self._empty_result(
                {
                    "status": "disabled",
                    "config": self._describe_config(),
                }
            )

        self._prepare_runtime_env()

        metadata_payload: dict[str, Any] = {
            "status": "starting",
            "python_packages": self._describe_packages(),
            "request_debug": self._describe_request(request),
            "config": self._describe_config(),
            "runtime_env": {
                "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": os.environ.get(
                    "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"
                ),
                "FLAGS_use_mkldnn": os.environ.get("FLAGS_use_mkldnn"),
                "FLAGS_enable_pir_api": os.environ.get("FLAGS_enable_pir_api"),
                "FLAGS_enable_pir_in_executor": os.environ.get(
                    "FLAGS_enable_pir_in_executor"
                ),
                "FLAGS_pir_apply_inplace_pass": os.environ.get(
                    "FLAGS_pir_apply_inplace_pass"
                ),
            },
        }

        try:
            image_np = self._resolve_image_np(request)
            metadata_payload["resolved_image_shape"] = list(image_np.shape)
            metadata_payload["resolved_image_dtype"] = str(image_np.dtype)
        except Exception as exc:
            metadata_payload["status"] = "image_resolve_error"
            metadata_payload["error"] = {
                "stage": "image_resolve",
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
            return self._empty_result(metadata_payload)

        try:
            ocr = self._get_or_create_ocr()
            metadata_payload["init"] = self._init_metadata
        except Exception as exc:
            metadata_payload["status"] = "init_error"
            metadata_payload["error"] = {
                "stage": "init",
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
            return self._empty_result(metadata_payload)

        try:
            raw_items = list(ocr.predict(image_np))
            metadata_payload["raw_item_types"] = [
                type(item).__name__
                for item in raw_items
            ]
            metadata_payload["raw_items_count"] = len(raw_items)
        except Exception as exc:
            metadata_payload["status"] = "predict_error"
            metadata_payload["error"] = {
                "stage": "predict",
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
            return self._empty_result(metadata_payload)

        parsed_items = self._parse_raw_items(raw_items)
        parsed_items = self._sort_items(parsed_items)

        metadata_payload["parsed_items_count"] = len(parsed_items)

        blocks: list[OCRBlock] = []
        raw_text_parts: list[str] = []
        confidence_values: list[float] = []

        for index, item in enumerate(parsed_items):
            text = item["text"].strip()
            if not text:
                continue

            score = self._safe_float(item["score"])
            bbox = item["bbox"]

            block = OCRBlock(
                text=text,
                confidence=score,
                bbox=bbox,
                lines=[],
                block_type="unknown",
                reading_order=index,
                source=self.name,
            )

            blocks.append(block)
            raw_text_parts.append(text)
            confidence_values.append(score)

        raw_text = "\n".join(raw_text_parts).strip()
        confidence = 0.0
        if confidence_values:
            confidence = sum(confidence_values) / len(confidence_values)

        metadata_payload["status"] = "ok"
        metadata_payload["items_preview"] = [
            {
                "text": item["text"],
                "score": round(self._safe_float(item["score"]), 4),
                "bbox": item["bbox"],
            }
            for item in parsed_items[:20]
        ]
        metadata_payload["raw_preview"] = self._summarize_raw_items(raw_items)

        if not raw_text and not blocks:
            metadata_payload["status"] = "empty_result"
            return self._empty_result(metadata_payload)

        return OCRBackendResult(
            backend_name=self.name,
            raw_text=raw_text,
            confidence=confidence,
            blocks=blocks,
            metadata=metadata_payload,
        )

    def _get_or_create_ocr(self) -> Any:
        if self._ocr is not None:
            return self._ocr

        try:
            from paddleocr import PaddleOCR
        except Exception as exc:
            raise RuntimeError(f"Could not import paddleocr: {exc}") from exc

        self._ocr = PaddleOCR(
            use_doc_orientation_classify=bool(
                self._config.enable_doc_orientation
            ),
            use_doc_unwarping=bool(self._config.enable_rectify),
            use_textline_orientation=bool(
                self._config.enable_textline_orientation
            ),
            device="gpu" if self._config.use_gpu else "cpu",
        )

        self._init_metadata = {
            "initialized": True,
            "engine_type": type(self._ocr).__name__,
            "device": "gpu" if self._config.use_gpu else "cpu",
            "use_doc_orientation_classify": self._config.enable_doc_orientation,
            "use_doc_unwarping": self._config.enable_rectify,
            "use_textline_orientation": self._config.enable_textline_orientation,
        }

        return self._ocr

    def _prepare_runtime_env(self) -> None:
        defaults = {
            "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True",
            "FLAGS_use_mkldnn": "0",
            "FLAGS_enable_pir_api": "0",
            "FLAGS_enable_pir_in_executor": "0",
            "FLAGS_pir_apply_inplace_pass": "0",
        }
        for key, value in defaults.items():
            os.environ.setdefault(key, value)

    def _resolve_image_np(self, request: OCRBackendRequest) -> np.ndarray:
        image_obj = request.image

        direct_candidates = [
            getattr(request, "image_path", None),
            getattr(request, "path", None),
            getattr(request, "bytes", None),
            image_obj,
        ]

        direct_candidates.extend(
            [
                getattr(image_obj, "file_path", None),
                getattr(image_obj, "path", None),
                getattr(image_obj, "source_path", None),
                getattr(image_obj, "original_path", None),
                getattr(image_obj, "local_path", None),
                getattr(image_obj, "image_path", None),
                getattr(image_obj, "array", None),
                getattr(image_obj, "image_np", None),
                getattr(image_obj, "numpy_image", None),
                getattr(image_obj, "np_image", None),
                getattr(image_obj, "bytes", None),
                getattr(image_obj, "content", None),
                getattr(image_obj, "data", None),
            ]
        )

        for candidate in direct_candidates:
            image_np = self._coerce_to_image_np(candidate)
            if image_np is not None:
                return image_np

        raise ValueError(
            "Could not resolve image from OCRBackendRequest. "
            f"Candidates={self._debug_candidates(direct_candidates)}"
        )

    def _coerce_to_image_np(self, candidate: Any) -> np.ndarray | None:
        if candidate is None:
            return None

        if isinstance(candidate, np.ndarray):
            return self._ensure_three_channels(candidate)

        if isinstance(candidate, Image.Image):
            return np.array(candidate.convert("RGB"))

        if isinstance(candidate, Path):
            if not candidate.exists():
                return None
            return np.array(Image.open(candidate).convert("RGB"))

        if isinstance(candidate, str):
            value = candidate.strip()
            if not value:
                return None
            path = Path(value)
            if not path.exists():
                return None
            return np.array(Image.open(path).convert("RGB"))

        if isinstance(candidate, (bytes, bytearray)):
            return np.array(Image.open(BytesIO(candidate)).convert("RGB"))

        return None

    def _ensure_three_channels(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return np.stack([image] * 3, axis=-1)

        if image.ndim == 3 and image.shape[2] == 1:
            return np.concatenate([image, image, image], axis=2)

        if image.ndim == 3 and image.shape[2] >= 3:
            return image[:, :, :3]

        raise ValueError(f"Unsupported image shape: {image.shape}")

    def _parse_raw_items(self, raw_items: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for raw_item in raw_items:
            raw_dict = self._result_to_dict(raw_item)
            if not raw_dict:
                continue

            payload = raw_dict.get("res", raw_dict)

            rec_texts = self._normalize_texts(payload.get("rec_texts"))
            rec_scores = self._normalize_scores(payload.get("rec_scores"))
            rec_polys = self._normalize_polys(
                payload.get("rec_polys") or payload.get("dt_polys")
            )
            rec_boxes = self._normalize_boxes(payload.get("rec_boxes"))

            count = max(
                len(rec_texts),
                len(rec_scores),
                len(rec_polys),
                len(rec_boxes),
            )

            for index in range(count):
                text = rec_texts[index] if index < len(rec_texts) else ""
                score = rec_scores[index] if index < len(rec_scores) else 0.0

                bbox: tuple[int, int, int, int] | None = None

                if index < len(rec_boxes):
                    bbox = rec_boxes[index]

                if bbox is None and index < len(rec_polys):
                    bbox = self._poly_to_bbox(rec_polys[index])

                if bbox is None:
                    continue

                result.append(
                    {
                        "text": text,
                        "score": score,
                        "bbox": bbox,
                    }
                )

        return result

    def _sort_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def sort_key(item: dict[str, Any]) -> tuple[int, int]:
            x, y, _w, _h = item["bbox"]
            return (y, x)

        sorted_items = sorted(items, key=sort_key)

        for index, item in enumerate(sorted_items):
            item["order"] = index

        return sorted_items

    def _result_to_dict(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value

        if hasattr(value, "json"):
            try:
                maybe_json = value.json
                if callable(maybe_json):
                    maybe_json = maybe_json()
                if isinstance(maybe_json, dict):
                    return maybe_json
            except Exception:
                pass

        if hasattr(value, "to_dict"):
            try:
                maybe_dict = value.to_dict()
                if isinstance(maybe_dict, dict):
                    return maybe_dict
            except Exception:
                pass

        if hasattr(value, "res"):
            res = getattr(value, "res")
            if isinstance(res, dict):
                return {"res": res}

        if hasattr(value, "__dict__"):
            maybe_dict = dict(value.__dict__)
            if isinstance(maybe_dict, dict):
                return maybe_dict

        return {}

    def _normalize_texts(self, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, np.ndarray):
            return [str(x) for x in value.tolist()]

        if isinstance(value, list):
            return [str(x) for x in value]

        return []

    def _normalize_scores(self, value: Any) -> list[float]:
        if value is None:
            return []

        if isinstance(value, np.ndarray):
            return [self._safe_float(x) for x in value.tolist()]

        if isinstance(value, list):
            return [self._safe_float(x) for x in value]

        return []

    def _normalize_polys(self, value: Any) -> list[list[list[int]]]:
        if value is None:
            return []

        if isinstance(value, np.ndarray):
            return value.astype(int).tolist()

        if isinstance(value, list):
            result: list[list[list[int]]] = []

            for poly in value:
                points = self._extract_points(poly)
                if not points:
                    continue

                result.append([[int(x), int(y)] for x, y in points])

            return result

        return []

    def _normalize_boxes(self, value: Any) -> list[tuple[int, int, int, int]]:
        if value is None:
            return []

        boxes: list[tuple[int, int, int, int]] = []

        if isinstance(value, np.ndarray):
            value = value.tolist()

        if not isinstance(value, list):
            return boxes

        for item in value:
            if (
                isinstance(item, list)
                and len(item) >= 4
                and self._is_number(item[0])
                and self._is_number(item[1])
                and self._is_number(item[2])
                and self._is_number(item[3])
            ):
                left = int(item[0])
                top = int(item[1])
                right = int(item[2])
                bottom = int(item[3])

                boxes.append(
                    (
                        left,
                        top,
                        max(1, right - left),
                        max(1, bottom - top),
                    )
                )

        return boxes

    def _poly_to_bbox(self, poly: Any) -> tuple[int, int, int, int] | None:
        points = self._extract_points(poly)
        if not points:
            return None

        xs = [point[0] for point in points]
        ys = [point[1] for point in points]

        left = int(min(xs))
        top = int(min(ys))
        right = int(max(xs))
        bottom = int(max(ys))

        return (left, top, max(1, right - left), max(1, bottom - top))

    def _extract_points(self, poly: Any) -> list[tuple[float, float]]:
        if hasattr(poly, "tolist"):
            poly = poly.tolist()

        if not isinstance(poly, list):
            return []

        points: list[tuple[float, float]] = []

        for item in poly:
            if (
                isinstance(item, list)
                and len(item) >= 2
                and self._is_number(item[0])
                and self._is_number(item[1])
            ):
                points.append((float(item[0]), float(item[1])))

        return points

    def _summarize_raw_items(self, raw_items: list[Any]) -> list[dict[str, Any]]:
        summary: list[dict[str, Any]] = []

        for item in raw_items[:3]:
            item_dict = self._result_to_dict(item)
            payload = item_dict.get("res", item_dict)

            if not isinstance(payload, dict):
                summary.append(
                    {
                        "keys": [],
                        "rec_texts_count": 0,
                        "rec_scores_count": 0,
                        "rec_boxes_count": 0,
                        "dt_polys_count": 0,
                    }
                )
                continue

            summary.append(
                {
                    "keys": list(payload.keys())[:20],
                    "rec_texts_count": len(payload.get("rec_texts", [])),
                    "rec_scores_count": len(payload.get("rec_scores", [])),
                    "rec_boxes_count": len(payload.get("rec_boxes", [])),
                    "dt_polys_count": len(payload.get("dt_polys", [])),
                }
            )

        return summary

    def _describe_config(self) -> dict[str, Any]:
        return {
            "configured": True,
            "enabled": self._config.enabled,
            "use_gpu": self._config.use_gpu,
            "timeout_seconds": self._config.timeout_seconds,
            "enable_textline_orientation": self._config.enable_textline_orientation,
            "enable_doc_orientation": self._config.enable_doc_orientation,
            "enable_rectify": self._config.enable_rectify,
            "det_model_dir": str(self._config.det_model_dir),
            "cls_model_dir": str(self._config.cls_model_dir),
            "rec_cyrillic_model_dir": str(self._config.rec_cyrillic_model_dir),
            "rec_latin_model_dir": str(self._config.rec_latin_model_dir),
            "rec_english_model_dir": str(self._config.rec_english_model_dir),
        }

    def _describe_request(self, request: OCRBackendRequest) -> dict[str, Any]:
        image = request.image

        return {
            "request_type": type(request).__name__,
            "has_image": image is not None,
            "image_type": type(image).__name__ if image is not None else None,
            "filename": getattr(image, "filename", None),
            "mime_type": getattr(image, "mime_type", None),
            "width": getattr(image, "width", None),
            "height": getattr(image, "height", None),
            "debug": request.debug,
        }

    def _debug_candidates(self, candidates: list[Any]) -> list[str]:
        result: list[str] = []

        for candidate in candidates:
            if candidate is None:
                continue

            if isinstance(candidate, (bytes, bytearray)):
                result.append(f"{type(candidate).__name__}(len={len(candidate)})")
                continue

            result.append(f"{type(candidate).__name__}: {repr(candidate)[:200]}")

        return result[:20]

    def _describe_packages(self) -> dict[str, Any]:
        return {
            "paddle": self._describe_package("paddle"),
            "paddleocr": self._describe_package("paddleocr"),
            "paddlex": self._describe_package("paddlex"),
        }

    def _describe_package(self, package_name: str) -> dict[str, Any]:
        try:
            version = importlib_metadata.version(package_name)
            return {
                "installed": True,
                "version": version,
            }
        except Exception:
            return {
                "installed": False,
                "version": None,
            }

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def _is_number(self, value: Any) -> bool:
        return isinstance(value, (int, float))

    def _empty_result(self, metadata_payload: dict[str, Any]) -> OCRBackendResult:
        return OCRBackendResult(
            backend_name=self.name,
            raw_text="",
            confidence=0.0,
            blocks=[],
            metadata=metadata_payload,
        )
        
