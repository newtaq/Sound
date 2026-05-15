from app.application.results import AIResultAttachmentExporter


def main() -> None:
    exporter = AIResultAttachmentExporter()

    text_attachment = exporter.text_attachment(
        filename="analysis_summary",
        text="Большой текстовый результат",
    )

    json_attachment = exporter.json_attachment(
        filename="analysis_raw",
        data={
            "content_type": "tour_announcement",
            "artist": "Кишлак",
        },
    )

    csv_attachment = exporter.csv_attachment(
        filename="events",
        rows=[
            {
                "artist": "Кишлак",
                "city": "Москва",
                "date": "2026-05-12",
                "venue": None,
            },
            {
                "artist": "Кишлак",
                "city": "Санкт-Петербург",
                "date": "2026-05-14",
                "venue": "A2",
            },
        ],
    )

    print("TEXT:", text_attachment.filename, text_attachment.mime_type, text_attachment.size_bytes)
    print("JSON:", json_attachment.filename, json_attachment.mime_type, json_attachment.size_bytes)
    print("CSV:", csv_attachment.filename, csv_attachment.mime_type, csv_attachment.size_bytes)
    print("CSV CONTENT:")
    print(csv_attachment.content.decode("utf-8-sig"))

    if text_attachment.filename != "analysis_summary.txt":
        raise SystemExit("Invalid text filename")

    if json_attachment.filename != "analysis_raw.json":
        raise SystemExit("Invalid json filename")

    if csv_attachment.filename != "events.csv":
        raise SystemExit("Invalid csv filename")

    if "Санкт-Петербург" not in csv_attachment.content.decode("utf-8-sig"):
        raise SystemExit("CSV content does not contain expected city")


if __name__ == "__main__":
    main()
    
