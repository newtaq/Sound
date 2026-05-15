from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, date, time
from pathlib import Path
from typing import Any

from app.application.posters.use_cases.extract_poster_draft import (
    ExtractPosterDraftUseCase,
)
from app.domain.posters.entities.poster_input import (
    PostButtonInput,
    PostImageInput,
    PosterInput,
)


SOURCE_ROOT = Path(r"D:\python\tg\SOUND")
OUTPUT_DIR = SOURCE_ROOT / "_poster_extract_results"
OUTPUT_FILE = OUTPUT_DIR / "poster_drafts.json"
ERRORS_FILE = OUTPUT_DIR / "poster_drafts_errors.json"


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    raw = value.strip()

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_plain(v) for k, v in asdict(value).items()}

    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}

    if isinstance(value, list):
        return [to_plain(v) for v in value]

    if isinstance(value, tuple):
        return [to_plain(v) for v in value]

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, time):
        return value.isoformat()

    if hasattr(value, "value"):
        return value.value

    return value


def extract_text_from_entity_list(items: list[Any]) -> str:
    parts: list[str] = []

    for item in items:
        if isinstance(item, str):
            parts.append(item)
            continue

        if not isinstance(item, dict):
            continue

        text = item.get("text")
        href = item.get("href")
        entity_type = item.get("type")

        if isinstance(text, str) and text:
            parts.append(text)

            if entity_type in {"link", "text_link"} and isinstance(href, str) and href:
                if href not in text:
                    parts.append(f" {href}")

    return "".join(parts).strip()


def extract_html_text_from_entity_list(items: list[Any]) -> str | None:
    parts: list[str] = []

    for item in items:
        if isinstance(item, str):
            parts.append(item)
            continue

        if not isinstance(item, dict):
            continue

        text = item.get("text")
        href = item.get("href")
        entity_type = item.get("type")

        if not isinstance(text, str):
            continue

        if entity_type == "bold":
            parts.append(f"<b>{text}</b>")
        elif entity_type == "italic":
            parts.append(f"<i>{text}</i>")
        elif entity_type == "spoiler":
            parts.append(f"<tg-spoiler>{text}</tg-spoiler>")
        elif entity_type in {"link", "text_link"} and isinstance(href, str) and href:
            parts.append(f'<a href="{href}">{text}</a>')
        else:
            parts.append(text)

    html = "".join(parts).strip()
    return html or None


def extract_message_text(message: dict[str, Any]) -> str:
    value = message.get("text")

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        return extract_text_from_entity_list(value)

    return ""


def extract_message_html(message: dict[str, Any]) -> str | None:
    value = message.get("text")

    if isinstance(value, list):
        return extract_html_text_from_entity_list(value)

    return None


def extract_buttons_from_entities(message: dict[str, Any]) -> list[PostButtonInput]:
    value = message.get("text")
    if not isinstance(value, list):
        return []

    buttons: list[PostButtonInput] = []
    seen: set[tuple[str | None, str]] = set()

    for item in value:
        if not isinstance(item, dict):
            continue

        entity_type = item.get("type")
        text = item.get("text")
        href = item.get("href")

        if entity_type not in {"link", "text_link"}:
            continue

        if not isinstance(href, str) or not href.strip():
            continue

        label = text.strip() if isinstance(text, str) and text.strip() else None
        key = (label, href.strip())

        if key in seen:
            continue

        seen.add(key)
        buttons.append(
            PostButtonInput(
                text=label,
                url=href.strip(),
            )
        )

    return buttons


def extract_images_from_message(message: dict[str, Any]) -> list[PostImageInput]:
    if "photo" not in message:
        return []

    width = safe_int(message.get("width")) or 0
    height = safe_int(message.get("height")) or 0
    file_size = safe_int(message.get("photo_file_size"))

    if width <= 0 or height <= 0:
        return []

    message_id = safe_int(message.get("id"))
    synthetic_file_id = f"photo_{message_id}" if message_id is not None else None
    synthetic_unique_id = f"photo_unique_{message_id}" if message_id is not None else None

    if not synthetic_file_id or not synthetic_unique_id:
        return []

    return [
        PostImageInput(
            telegram_file_id=synthetic_file_id,
            telegram_file_unique_id=synthetic_unique_id,
            width=width,
            height=height,
            file_size=file_size,
            position=0,
        )
    ]


def build_poster_input(
    message: dict[str, Any],
    channel_id: int | None,
) -> PosterInput | None:
    if message.get("type") != "message":
        return None

    text = extract_message_text(message)
    html_text = extract_message_html(message)

    if not text and not html_text:
        return None

    return PosterInput(
        text=text,
        html_text=html_text,
        buttons=extract_buttons_from_entities(message),
        images=extract_images_from_message(message),
        channel_id=channel_id,
        post_id=safe_int(message.get("id")),
        published_at=parse_datetime(message.get("date")),
    )


def process_file(
    use_case: ExtractPosterDraftUseCase,
    path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], [{"file": str(path), "error": f"json_read_error: {exc}"}]

    channel_id = safe_int(payload.get("id")) if isinstance(payload, dict) else None
    messages = payload.get("messages") if isinstance(payload, dict) else None

    if not isinstance(messages, list):
        return [], [{"file": str(path), "error": "messages_not_found"}]

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue

        try:
            poster_input = build_poster_input(message=message, channel_id=channel_id)
            if poster_input is None:
                continue

            poster_draft = use_case.execute(poster_input)

            results.append(
                {
                    "source_file": str(path),
                    "message_index": index,
                    "message_id": message.get("id"),
                    "message_date": message.get("date"),
                    "poster_input": to_plain(poster_input),
                    "poster_draft": to_plain(poster_draft),
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "file": str(path),
                    "message_index": index,
                    "message_id": message.get("id"),
                    "error": f"extract_error: {exc}",
                    "text_preview": extract_message_text(message)[:500],
                }
            )

    return results, errors


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    use_case = ExtractPosterDraftUseCase()

    all_results: list[dict[str, Any]] = []
    all_errors: list[dict[str, Any]] = []

    json_files = sorted(SOURCE_ROOT.rglob("*.json"))

    for path in json_files:
        results, errors = process_file(use_case=use_case, path=path)
        all_results.extend(results)
        all_errors.extend(errors)

    OUTPUT_FILE.write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ERRORS_FILE.write_text(
        json.dumps(all_errors, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Files: {len(json_files)}")
    print(f"Poster drafts: {len(all_results)}")
    print(f"Errors: {len(all_errors)}")
    print(f"Saved: {OUTPUT_FILE}")
    print(f"Saved: {ERRORS_FILE}")


if __name__ == "__main__":
    main()
    