"""Source previews preserve cell positions and do not normalize values."""

import io
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from openpyxl import Workbook

from app.modules.upload.raw_preview import raw_preview


class RawPreviewTests(unittest.TestCase):
    def test_excel_keeps_duplicate_blank_headers_and_first_five_rows(self):
        book = Workbook()
        sheet = book.active
        sheet.title = "Pilihan"
        sheet.append([" Nama ", "Nama", None, "IDPEL", "Catatan"])
        for index in range(7):
            sheet.append([f"  Nilai {index}  ", "-", "nan", "000123", 0])
        data = io.BytesIO()
        book.save(data)
        data.seek(0)
        result = raw_preview(data, "data.xlsx", "Pilihan")
        self.assertEqual(result["headers"], [" Nama ", "Nama", None, "IDPEL", "Catatan"])
        self.assertEqual(len(result["rows"]), 5)
        self.assertEqual(result["rows"][0], ["  Nilai 0  ", "-", "nan", "000123", 0])
        self.assertEqual(result["rows"][-1][0], "  Nilai 4  ")

    def test_excel_requires_explicit_sheet_and_reads_only_selected_sheet(self):
        book = Workbook()
        book.active.title = "Jangan dipilih"
        book.active.append(["Lain"])
        chosen = book.create_sheet("Dipilih")
        chosen.append(["Asli"])
        chosen.append(["Benar"])
        data = io.BytesIO()
        book.save(data)
        data.seek(0)
        with self.assertRaisesRegex(ValueError, "Pilih sheet"):
            raw_preview(data, "data.xlsx", None)
        data.seek(0)
        result = raw_preview(data, "data.xlsx", "Dipilih")
        self.assertEqual(result["headers"], ["Asli"])
        self.assertEqual(result["rows"], [["Benar"]])

    def test_csv_keeps_blank_cells_leading_zeroes_and_literal_values(self):
        data = io.BytesIO("Nama;Nama;;IDPEL\n  A  ;-;nan;000123\nB;;0;000124\n".encode())
        result = raw_preview(data, "data.csv", None)
        self.assertEqual(result["headers"], ["Nama", "Nama", "", "IDPEL"])
        self.assertEqual(result["rows"], [["  A  ", "-", "nan", "000123"], ["B", "", "0", "000124"]])

    def test_excel_retains_blank_rows_between_data_rows(self):
        book = Workbook()
        sheet = book.active
        sheet.append(["Kolom"])
        sheet.append(["A"])
        sheet.append([None])
        sheet.append(["B"])
        data = io.BytesIO()
        book.save(data)
        data.seek(0)
        self.assertEqual(raw_preview(data, "data.xlsx", sheet.title)["rows"], [["A"], [None], ["B"]])


if __name__ == "__main__":
    unittest.main()
