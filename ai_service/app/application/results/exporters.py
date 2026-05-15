import csv
import json
from io import BytesIO, StringIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from app.application.results.attachments import (
    AIResultAttachment,
    AIResultAttachmentType,
)


class AIResultAttachmentExporter:
    def text_attachment(
        self,
        filename: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> AIResultAttachment:
        return AIResultAttachment(
            filename=self._ensure_extension(filename, ".txt"),
            mime_type="text/plain",
            attachment_type=AIResultAttachmentType.TEXT,
            content=text.encode("utf-8"),
            metadata=metadata or {},
        )

    def json_attachment(
        self,
        filename: str,
        data: Any,
        metadata: dict[str, Any] | None = None,
    ) -> AIResultAttachment:
        content = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

        return AIResultAttachment(
            filename=self._ensure_extension(filename, ".json"),
            mime_type="application/json",
            attachment_type=AIResultAttachmentType.JSON,
            content=content.encode("utf-8"),
            metadata=metadata or {},
        )

    def csv_attachment(
        self,
        filename: str,
        rows: list[dict[str, Any]],
        headers: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AIResultAttachment:
        selected_headers = headers or self._collect_headers(rows)

        output = StringIO(newline="")
        writer = csv.DictWriter(
            output,
            fieldnames=selected_headers,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    header: self._csv_value(row.get(header))
                    for header in selected_headers
                }
            )

        return AIResultAttachment(
            filename=self._ensure_extension(filename, ".csv"),
            mime_type="text/csv",
            attachment_type=AIResultAttachmentType.CSV,
            content=output.getvalue().encode("utf-8-sig"),
            metadata=metadata or {},
        )

    def excel_attachment(
        self,
        filename: str,
        rows: list[dict[str, Any]],
        headers: list[str] | None = None,
        sheet_name: str = "Results",
        metadata: dict[str, Any] | None = None,
    ) -> AIResultAttachment:
        selected_headers = headers or self._collect_headers(rows)
        content = self._build_xlsx(
            rows=rows,
            headers=selected_headers,
            sheet_name=sheet_name,
        )

        return AIResultAttachment(
            filename=self._ensure_extension(filename, ".xlsx"),
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            attachment_type=AIResultAttachmentType.EXCEL,
            content=content,
            metadata=metadata or {},
        )

    def _build_xlsx(
        self,
        rows: list[dict[str, Any]],
        headers: list[str],
        sheet_name: str,
    ) -> bytes:
        output = BytesIO()

        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self._xlsx_content_types())
            archive.writestr("_rels/.rels", self._xlsx_root_rels())
            archive.writestr("xl/workbook.xml", self._xlsx_workbook(sheet_name))
            archive.writestr("xl/_rels/workbook.xml.rels", self._xlsx_workbook_rels())
            archive.writestr("xl/styles.xml", self._xlsx_styles())
            archive.writestr("xl/worksheets/sheet1.xml", self._xlsx_sheet(rows, headers))

        return output.getvalue()

    def _xlsx_content_types(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

    def _xlsx_root_rels(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    def _xlsx_workbook(self, sheet_name: str) -> str:
        safe_sheet_name = escape(sheet_name[:31] or "Results")

        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{safe_sheet_name}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

    def _xlsx_workbook_rels(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    def _xlsx_styles(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/></font>
  </fonts>
  <fills count="1">
    <fill><patternFill patternType="none"/></fill>
  </fills>
  <borders count="1">
    <border><left/><right/><top/><bottom/><diagonal/></border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
  </cellXfs>
</styleSheet>"""

    def _xlsx_sheet(self, rows: list[dict[str, Any]], headers: list[str]) -> str:
        xml_rows: list[str] = []

        header_cells = [
            self._xlsx_cell(
                row_index=1,
                column_index=column_index,
                value=header,
                style_id=1,
            )
            for column_index, header in enumerate(headers, start=1)
        ]
        xml_rows.append(f'<row r="1">{"".join(header_cells)}</row>')

        for row_index, row in enumerate(rows, start=2):
            cells = [
                self._xlsx_cell(
                    row_index=row_index,
                    column_index=column_index,
                    value=row.get(header),
                    style_id=0,
                )
                for column_index, header in enumerate(headers, start=1)
            ]
            xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

        dimension_end = self._xlsx_cell_ref(
            row_index=max(len(rows) + 1, 1),
            column_index=max(len(headers), 1),
        )

        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:{dimension_end}"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>{self._xlsx_columns(headers)}</cols>
  <sheetData>
    {''.join(xml_rows)}
  </sheetData>
</worksheet>"""

    def _xlsx_columns(self, headers: list[str]) -> str:
        columns: list[str] = []

        for index, header in enumerate(headers, start=1):
            width = min(max(len(header) + 4, 12), 36)
            columns.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')

        return "".join(columns)

    def _xlsx_cell(
        self,
        row_index: int,
        column_index: int,
        value: Any,
        style_id: int,
    ) -> str:
        cell_ref = self._xlsx_cell_ref(row_index, column_index)
        text = escape(self._csv_value(value))

        return f'<c r="{cell_ref}" t="inlineStr" s="{style_id}"><is><t>{text}</t></is></c>'

    def _xlsx_cell_ref(self, row_index: int, column_index: int) -> str:
        return f"{self._xlsx_column_name(column_index)}{row_index}"

    def _xlsx_column_name(self, column_index: int) -> str:
        result = ""

        while column_index > 0:
            column_index, remainder = divmod(column_index - 1, 26)
            result = chr(65 + remainder) + result

        return result

    def _collect_headers(self, rows: list[dict[str, Any]]) -> list[str]:
        headers: list[str] = []

        for row in rows:
            for key in row:
                if key not in headers:
                    headers.append(key)

        return headers

    def _csv_value(self, value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value

        if isinstance(value, int | float | bool):
            return str(value)

        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )

    def _ensure_extension(self, filename: str, extension: str) -> str:
        if filename.lower().endswith(extension):
            return filename

        return f"{filename}{extension}"
    

