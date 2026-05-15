from app.application.results import AIResultAutoExporter


def main() -> None:
    auto_exporter = AIResultAutoExporter(
        inline_text_limit=50,
        inline_rows_limit=2,
    )

    small_text = auto_exporter.from_text(
        text="Короткий результат",
        filename="small_result",
    )

    large_text = auto_exporter.from_text(
        text="Очень большой результат. " * 20,
        filename="large_result",
    )

    rows = [
        {
            "artist": "Кишлак",
            "city": "Москва",
            "date": "2026-05-12",
        },
        {
            "artist": "Кишлак",
            "city": "Санкт-Петербург",
            "date": "2026-05-14",
        },
        {
            "artist": "Кишлак",
            "city": "Казань",
            "date": "2026-05-16",
        },
    ]

    table_result = auto_exporter.from_rows(
        rows=rows,
        filename="events",
        title="Список событий",
    )

    print("SMALL TEXT ATTACHMENTS:", len(small_text.attachments))
    print("LARGE TEXT ATTACHMENTS:", len(large_text.attachments))
    print("LARGE TEXT FILENAME:", large_text.attachments[0].filename)
    print("TABLE ATTACHMENTS:", len(table_result.attachments))
    print("TABLE TEXT:", table_result.text)

    if small_text.has_attachments:
        raise SystemExit("Small text should not have attachments")

    if len(large_text.attachments) != 1:
        raise SystemExit("Large text should have one attachment")

    if large_text.attachments[0].filename != "large_result.txt":
        raise SystemExit("Large text attachment filename is invalid")

    if len(table_result.attachments) != 2:
        raise SystemExit("Large table should have two attachments")

    filenames = {attachment.filename for attachment in table_result.attachments}

    if "events.xlsx" not in filenames:
        raise SystemExit("XLSX attachment is missing")

    if "events_raw.json" not in filenames:
        raise SystemExit("JSON attachment is missing")


if __name__ == "__main__":
    main()
    
