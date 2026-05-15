from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SOURCE_ROOT = Path(r"D:\python\tg\SOUND")
INPUT_FILE = SOURCE_ROOT / "_poster_extract_results" / "poster_drafts.json"
OUTPUT_FILE = SOURCE_ROOT / "_poster_extract_results" / "poster_occurrence_failures.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_occurrence_failure(record: dict[str, Any]) -> bool:
    draft = record.get("poster_draft")
    if not isinstance(draft, dict):
        return False

    warnings = draft.get("warnings")
    if not isinstance(warnings, list):
        return False

    return "Failed to extract occurrence data" in warnings


def build_failure_entry(record: dict[str, Any]) -> dict[str, Any]:
    draft = record.get("poster_draft", {})
    poster_input = record.get("poster_input", {})

    return {
        "source_file": record.get("source_file"),
        "message_index": record.get("message_index"),
        "message_id": record.get("message_id"),
        "title": draft.get("title"),
        "artist_names": draft.get("artist_names"),
        "ticket_links": draft.get("ticket_links"),
        "warnings": draft.get("warnings"),
        "raw_text": poster_input.get("text") or draft.get("raw_text"),
        "html_text": poster_input.get("html_text"),
        "buttons": poster_input.get("buttons"),
        "images": poster_input.get("images"),
        "poster_draft": draft,
    }


def main() -> None:
    records = load_json(INPUT_FILE)
    if not isinstance(records, list):
        raise ValueError("poster_drafts.json must contain a list")

    failures = [
        build_failure_entry(record)
        for record in records
        if isinstance(record, dict) and is_occurrence_failure(record)
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(failures, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Input file: {INPUT_FILE}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Occurrence failures exported: {len(failures)}")


if __name__ == "__main__":
    main()
    