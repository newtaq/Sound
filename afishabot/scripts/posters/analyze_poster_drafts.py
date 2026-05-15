from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SOURCE_ROOT = Path(r"D:\python\tg\SOUND")
INPUT_FILE = SOURCE_ROOT / "_poster_extract_results" / "poster_drafts.json"
OUTPUT_FILE = SOURCE_ROOT / "_poster_extract_results" / "poster_drafts_report.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def has_title(draft: dict[str, Any]) -> bool:
    value = draft.get("title")
    return isinstance(value, str) and bool(value.strip())


def has_artists(draft: dict[str, Any]) -> bool:
    value = draft.get("artist_names")
    return isinstance(value, list) and any(isinstance(x, str) and x.strip() for x in value)


def has_occurrences(draft: dict[str, Any]) -> bool:
    value = draft.get("occurrences")
    return isinstance(value, list) and len(value) > 0


def has_date(draft: dict[str, Any]) -> bool:
    occurrences = draft.get("occurrences")
    if not isinstance(occurrences, list):
        return False

    for occurrence in occurrences:
        if not isinstance(occurrence, dict):
            continue
        if occurrence.get("event_date"):
            return True

    return False


def has_venue(draft: dict[str, Any]) -> bool:
    occurrences = draft.get("occurrences")
    if not isinstance(occurrences, list):
        return False

    for occurrence in occurrences:
        if not isinstance(occurrence, dict):
            continue
        venue_name = occurrence.get("venue_name")
        if isinstance(venue_name, str) and venue_name.strip():
            return True

    return False


def has_city(draft: dict[str, Any]) -> bool:
    occurrences = draft.get("occurrences")
    if not isinstance(occurrences, list):
        return False

    for occurrence in occurrences:
        if not isinstance(occurrence, dict):
            continue
        city_name = occurrence.get("city_name")
        if isinstance(city_name, str) and city_name.strip():
            return True

    return False


def has_ticket_link(draft: dict[str, Any]) -> bool:
    links = draft.get("ticket_links")
    if not isinstance(links, list):
        return False

    for link in links:
        if not isinstance(link, dict):
            continue

        link_type = link.get("link_type")
        url = link.get("url")

        if link_type == "ticket" and isinstance(url, str) and url.strip():
            return True

    return False


def has_chat_link(draft: dict[str, Any]) -> bool:
    links = draft.get("ticket_links")
    if not isinstance(links, list):
        return False

    for link in links:
        if not isinstance(link, dict):
            continue

        link_type = link.get("link_type")
        url = link.get("url")

        if link_type == "chat" and isinstance(url, str) and url.strip():
            return True

    return False


def has_external_link(draft: dict[str, Any]) -> bool:
    links = draft.get("ticket_links")
    if not isinstance(links, list):
        return False

    for link in links:
        if not isinstance(link, dict):
            continue

        link_type = link.get("link_type")
        url = link.get("url")

        if link_type == "external" and isinstance(url, str) and url.strip():
            return True

    return False


def has_description(draft: dict[str, Any]) -> bool:
    value = draft.get("description")
    return isinstance(value, str) and bool(value.strip())


def has_warnings(draft: dict[str, Any]) -> bool:
    warnings = draft.get("warnings")
    return isinstance(warnings, list) and len(warnings) > 0


def collect_warning_values(draft: dict[str, Any]) -> list[str]:
    warnings = draft.get("warnings")
    if not isinstance(warnings, list):
        return []

    result: list[str] = []
    for warning in warnings:
        if isinstance(warning, str) and warning.strip():
            result.append(warning.strip())

    return result


def classify_record(draft: dict[str, Any]) -> list[str]:
    tags: list[str] = []

    if not has_title(draft):
        tags.append("missing_title")

    if not has_artists(draft):
        tags.append("missing_artists")

    if not has_occurrences(draft):
        tags.append("missing_occurrences")

    if not has_date(draft):
        tags.append("missing_date")

    if not has_venue(draft):
        tags.append("missing_venue")

    if not has_city(draft):
        tags.append("missing_city")

    if not has_ticket_link(draft):
        tags.append("missing_ticket_link")

    if not has_description(draft):
        tags.append("missing_description")

    if has_warnings(draft):
        tags.append("has_warnings")

    return tags


def analyze(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)

    summary = {
        "total_records": total,
        "with_title": 0,
        "with_artists": 0,
        "with_occurrences": 0,
        "with_date": 0,
        "with_venue": 0,
        "with_city": 0,
        "with_ticket_link": 0,
        "with_chat_link": 0,
        "with_external_link": 0,
        "with_description": 0,
        "with_warnings": 0,
    }

    tag_counter: Counter[str] = Counter()
    warning_counter: Counter[str] = Counter()
    file_problem_counter: Counter[str] = Counter()
    file_total_counter: Counter[str] = Counter()
    examples_by_tag: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        source_file = record.get("source_file")
        poster_draft = record.get("poster_draft")

        if not isinstance(source_file, str):
            source_file = "<unknown>"

        if not isinstance(poster_draft, dict):
            continue

        file_total_counter[source_file] += 1

        if has_title(poster_draft):
            summary["with_title"] += 1
        if has_artists(poster_draft):
            summary["with_artists"] += 1
        if has_occurrences(poster_draft):
            summary["with_occurrences"] += 1
        if has_date(poster_draft):
            summary["with_date"] += 1
        if has_venue(poster_draft):
            summary["with_venue"] += 1
        if has_city(poster_draft):
            summary["with_city"] += 1
        if has_ticket_link(poster_draft):
            summary["with_ticket_link"] += 1
        if has_chat_link(poster_draft):
            summary["with_chat_link"] += 1
        if has_external_link(poster_draft):
            summary["with_external_link"] += 1
        if has_description(poster_draft):
            summary["with_description"] += 1
        if has_warnings(poster_draft):
            summary["with_warnings"] += 1

        tags = classify_record(poster_draft)
        if tags:
            file_problem_counter[source_file] += 1

        for tag in tags:
            tag_counter[tag] += 1

            if len(examples_by_tag[tag]) < 20:
                examples_by_tag[tag].append(
                    {
                        "source_file": source_file,
                        "message_index": record.get("message_index"),
                        "message_id": record.get("message_id"),
                        "title": poster_draft.get("title"),
                        "warnings": poster_draft.get("warnings"),
                        "occurrences": poster_draft.get("occurrences"),
                        "artist_names": poster_draft.get("artist_names"),
                        "ticket_links": poster_draft.get("ticket_links"),
                    }
                )

        for warning in collect_warning_values(poster_draft):
            warning_counter[warning] += 1

    file_stats: list[dict[str, Any]] = []
    for file_path, total_count in file_total_counter.items():
        problem_count = file_problem_counter[file_path]
        problem_ratio = 0.0
        if total_count > 0:
            problem_ratio = round(problem_count / total_count, 4)

        file_stats.append(
            {
                "source_file": file_path,
                "total_records": total_count,
                "records_with_any_problem": problem_count,
                "problem_ratio": problem_ratio,
            }
        )

    file_stats.sort(
        key=lambda item: (
            -item["records_with_any_problem"],
            -item["problem_ratio"],
            item["source_file"],
        )
    )

    return {
        "summary": summary,
        "tag_counts": dict(tag_counter.most_common()),
        "warning_counts": dict(warning_counter.most_common()),
        "top_problem_files": file_stats[:100],
        "examples_by_tag": dict(examples_by_tag),
    }


def main() -> None:
    records = load_json(INPUT_FILE)
    if not isinstance(records, list):
        raise ValueError("poster_drafts.json must contain a list")

    report = analyze(records)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = report["summary"]

    print(f"Input file: {INPUT_FILE}")
    print(f"Output file: {OUTPUT_FILE}")
    print()
    print(f"Total records: {summary['total_records']}")
    print(f"With title: {summary['with_title']}")
    print(f"With artists: {summary['with_artists']}")
    print(f"With occurrences: {summary['with_occurrences']}")
    print(f"With date: {summary['with_date']}")
    print(f"With venue: {summary['with_venue']}")
    print(f"With city: {summary['with_city']}")
    print(f"With ticket link: {summary['with_ticket_link']}")
    print(f"With chat link: {summary['with_chat_link']}")
    print(f"With external link: {summary['with_external_link']}")
    print(f"With description: {summary['with_description']}")
    print(f"With warnings: {summary['with_warnings']}")
    print()
    print("Top tags:")
    for tag, count in list(report["tag_counts"].items())[:15]:
        print(f"  {tag}: {count}")
    print()
    print("Top warnings:")
    for warning, count in list(report["warning_counts"].items())[:15]:
        print(f"  {warning}: {count}")


if __name__ == "__main__":
    main()
    