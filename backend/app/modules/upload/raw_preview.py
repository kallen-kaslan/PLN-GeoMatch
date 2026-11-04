"""Read a small source table without normalizing headers or cell contents."""

import codecs
import csv
import io
from itertools import islice
from typing import Any, BinaryIO

from openpyxl import load_workbook

from .normalization import clean_text
from .reader import detect_csv_encoding


def raw_preview(source: BinaryIO, filename: str, sheet_name: str | None) -> dict[str, Any]:
    if filename.lower().endswith(".csv"):
        encoding = detect_csv_encoding(source)
        sample = codecs.getincrementaldecoder(encoding)().decode(source.read(32768), final=False)
        source.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
        text = io.TextIOWrapper(source, encoding=encoding, newline="")
        try:
            reader = csv.reader(text, delimiter=delimiter)
            headers = next(reader, [])
            rows = list(islice(reader, 5))
        finally:
            text.detach()
        header_row = 1
    else:
        if not sheet_name:
            raise ValueError("Pilih sheet yang ingin ditampilkan")
        book = load_workbook(source, read_only=True, data_only=True)
        try:
            if sheet_name not in book.sheetnames:
                raise ValueError("Sheet tidak ditemukan")
            sheet = book[sheet_name]
            sheet.reset_dimensions()
            iterator = enumerate(sheet.iter_rows(values_only=True), start=1)
            headers, header_row = [], 1
            for number, values in iterator:
                if any(clean_text(value) for value in values):
                    headers, header_row = list(values), number
                    break
            rows = [list(values) for _, values in islice(iterator, 5)]
        finally:
            book.close()
    # Retain unnamed columns and positions, including cells beyond header width.
    width = max([len(headers), *(len(row) for row in rows)])
    return {
        "headers": headers + [None] * (width - len(headers)),
        "rows": [row + [None] * (width - len(row)) for row in rows],
        "header_row": header_row,
    }
