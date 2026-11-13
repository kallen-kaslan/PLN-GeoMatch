"""Build plain XLSX tables while preserving identifier and coordinate text."""

from collections.abc import Iterator, Sequence
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, cast

from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.utils import get_column_letter
from openpyxl.worksheet._write_only import WriteOnlyWorksheet

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CANDIDATE_DISTANCE_HEADER = "Jarak Kandidat (m)"
DISTANCE_NUMBER_FORMAT = '0.00" m"'
RESULT_HEADERS = [
    "objectid",
    "noagenda",
    "idpelanggan",
    "jenispelanggan",
    "latitudey",
    "longitudex",
    "sumber file (sheet)",
    "sel (baris ke berapa)",
    "x_akhir",
    "y_akhir",
    "radius_pemeriksaan_meter",
    CANDIDATE_DISTANCE_HEADER,
]
RESULT_WIDTHS = [16, 26, 22, 22, 24, 24, 58, 26, 24, 24, 30, 26]


class Spreadsheet:
    """Write rows incrementally; never interpret uploaded strings as formulas."""

    def __init__(self) -> None:
        self.book = Workbook(write_only=True)
        self.book.properties.creator = "PLN GeoMatch"
        self.number_formats: dict[str, dict[int, str]] = {}

    def sheet(
        self,
        title: str,
        headers: Sequence[str],
        widths: Sequence[int],
        number_formats: dict[str, str] | None = None,
    ) -> WriteOnlyWorksheet:
        sheet = self.book.create_sheet(title)
        self.number_formats[sheet.title] = {
            index: number_formats[header]
            for index, header in enumerate(headers)
            if number_formats and header in number_formats
        }
        for index, width in enumerate(widths, 1):
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.append(list(headers))
        return sheet

    def append(self, sheet: WriteOnlyWorksheet, values: Sequence[Any]) -> None:
        cells = []
        formats = self.number_formats.get(sheet.title, {})
        for index, value in enumerate(values):
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str):
                # XLSX strings preserve leading zeroes, decimal digits, and literal '='.
                cell.data_type = "s"
                cell.number_format = "@"
            elif isinstance(value, (int, float)) and index in formats:
                cell.number_format = formats[index]
            cells.append(cell)
        sheet.append(cells)

    def response(self, filename: str) -> StreamingResponse:
        output = cast(
            BinaryIO,
            SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b"),  # noqa: SIM115 -- response closes it
        )
        try:
            self.book.save(output)
            output.seek(0)
        except BaseException:
            output.close()
            raise

        def content() -> Iterator[bytes]:
            try:
                while chunk := output.read(64 * 1024):
                    yield chunk
            finally:
                output.close()

        return StreamingResponse(
            content(),
            media_type=XLSX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
