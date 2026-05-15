from typing import Any

from app.application.results.attachments import AIResultWithAttachments
from app.application.results.exporters import AIResultAttachmentExporter


class AIResultAutoExporter:
    def __init__(
        self,
        exporter: AIResultAttachmentExporter | None = None,
        inline_text_limit: int = 3500,
        inline_rows_limit: int = 20,
    ) -> None:
        self._exporter = exporter or AIResultAttachmentExporter()
        self._inline_text_limit = inline_text_limit
        self._inline_rows_limit = inline_rows_limit

    def from_text(
        self,
        text: str,
        filename: str = "result",
        metadata: dict[str, Any] | None = None,
    ) -> AIResultWithAttachments:
        if len(text) <= self._inline_text_limit:
            return AIResultWithAttachments(
                text=text,
                attachments=[],
                metadata=metadata or {},
            )

        preview = text[: self._inline_text_limit].rstrip()

        return AIResultWithAttachments(
            text=(
                f"{preview}\n\n"
                f"[Результат слишком большой: {len(text)} символов. "
                f"Полная версия вынесена во вложение.]"
            ),
            attachments=[
                self._exporter.text_attachment(
                    filename=filename,
                    text=text,
                    metadata={
                        "kind": "full_text_result",
                        "original_length": len(text),
                    },
                )
            ],
            metadata={
                **(metadata or {}),
                "auto_exported": True,
                "export_reason": "text_too_large",
                "original_length": len(text),
            },
        )

    def from_rows(
        self,
        rows: list[dict[str, Any]],
        filename: str = "results",
        title: str = "Результаты",
        headers: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AIResultWithAttachments:
        if len(rows) <= self._inline_rows_limit:
            return AIResultWithAttachments(
                text=self._rows_preview_text(
                    rows=rows,
                    title=title,
                    headers=headers,
                ),
                attachments=[],
                metadata={
                    **(metadata or {}),
                    "rows_count": len(rows),
                    "auto_exported": False,
                },
            )

        return AIResultWithAttachments(
            text=(
                f"{title}\n\n"
                f"Найдено строк: {len(rows)}.\n"
                f"Результат большой, поэтому таблица вынесена во вложения: XLSX + JSON."
            ),
            attachments=[
                self._exporter.excel_attachment(
                    filename=filename,
                    rows=rows,
                    headers=headers,
                    sheet_name="Results",
                    metadata={
                        "kind": "table_result",
                        "rows_count": len(rows),
                    },
                ),
                self._exporter.json_attachment(
                    filename=f"{filename}_raw",
                    data=rows,
                    metadata={
                        "kind": "raw_table_result",
                        "rows_count": len(rows),
                    },
                ),
            ],
            metadata={
                **(metadata or {}),
                "rows_count": len(rows),
                "auto_exported": True,
                "export_reason": "too_many_rows",
            },
        )

    def _rows_preview_text(
        self,
        rows: list[dict[str, Any]],
        title: str,
        headers: list[str] | None,
    ) -> str:
        if not rows:
            return f"{title}\n\nНет данных."

        selected_headers = headers or self._collect_headers(rows)

        lines = [
            title,
            "",
            f"Строк: {len(rows)}",
            "",
            " | ".join(selected_headers),
            " | ".join("---" for _ in selected_headers),
        ]

        for row in rows:
            lines.append(
                " | ".join(
                    self._inline_value(row.get(header))
                    for header in selected_headers
                )
            )

        return "\n".join(lines)

    def _collect_headers(self, rows: list[dict[str, Any]]) -> list[str]:
        headers: list[str] = []

        for row in rows:
            for key in row:
                if key not in headers:
                    headers.append(key)

        return headers

    def _inline_value(self, value: Any) -> str:
        if value is None:
            return ""

        text = str(value).replace("\n", " ").strip()

        if len(text) <= 80:
            return text

        return f"{text[:77]}..."
    

