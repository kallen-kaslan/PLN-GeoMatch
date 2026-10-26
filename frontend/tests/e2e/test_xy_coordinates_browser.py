"""PLN reverse X/Y and conventional X/Y survive import and file-history reuse."""

from io import BytesIO

import httpx
from openpyxl import Workbook
from playwright.sync_api import Page, expect


def test_pln_xy_detection_and_history_sheet_with_standard_order(
    page: Page, servers: tuple[str, str]
) -> None:
    book = Workbook()
    book.active.title = "PLN"
    book.active.append(["IDPEL", "KOORDINAT_X", "KOORDINAT_Y"])
    book.active.append(["001", "-6,78792521", "108,57478594"])
    standard = book.create_sheet("Standar")
    standard.append(["IDPEL", "KOORDINAT_X", "KOORDINAT_Y"])
    standard.append(["002", 108.5, -6.2])
    stream = BytesIO()
    book.save(stream)
    page.goto("/master/dil")
    page.get_by_role("button", name="Unggah berkas", exact=True).click()
    page.locator("input[type=file]").set_input_files(
        {
            "name": "xy.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": stream.getvalue(),
        }
    )
    expect(page.get_by_label("Kolom Latitude (lintang)", exact=True)).to_have_value(
        "KOORDINAT_X", timeout=20000
    )
    expect(page.get_by_label("Kolom Longitude (bujur)", exact=True)).to_have_value(
        "KOORDINAT_Y"
    )
    save = page.get_by_role("button", name="Simpan dan validasi master", exact=True)
    save.click()
    expect(page.get_by_text("xy.xlsx berhasil disimpan.", exact=True)).to_be_visible(
        timeout=20000
    )
    rows = httpx.get(servers[1] + "/master/dil/records").json()["items"]
    assert rows[0]["fields"]["lat"] == -6.78792521
    assert rows[0]["fields"]["lon"] == 108.57478594
    assert rows[0]["is_valid"] and rows[0]["coordinates_complete"]
    page.get_by_role("button", name="Unggah berkas", exact=True).click()
    page.get_by_label("Riwayat berkas unggahan", exact=True).select_option(index=1)
    page.get_by_label("Sheet yang diimpor", exact=True).select_option("Standar")
    expect(page.get_by_label("Kolom Latitude (lintang)", exact=True)).to_have_value(
        "KOORDINAT_Y"
    )
    expect(page.get_by_label("Kolom Longitude (bujur)", exact=True)).to_have_value(
        "KOORDINAT_X"
    )
    save.click()
    expect(page.get_by_role("region", name="Impor master DIL", exact=True)).to_have_count(0, timeout=20000)
    expect(page.get_by_text("xy.xlsx berhasil disimpan.", exact=True)).to_be_visible(
        timeout=20000
    )
    rows = httpx.get(servers[1] + "/master/dil/records").json()["items"]
    assert len(rows) == 2 and all(
        row["coordinates_complete"] and row["is_valid"] for row in rows
    )
    standard_row = next(row for row in rows if row["fields"]["idpel"] == "002")
    assert (
        standard_row["fields"]["lat"] == -6.2 and standard_row["fields"]["lon"] == 108.5
    )
