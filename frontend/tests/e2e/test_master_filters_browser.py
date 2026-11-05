"""Master condition changes preserve search, file scope, and counts."""

import pytest
from playwright.sync_api import Page, expect

from test_corrections_browser import upload


@pytest.mark.parametrize("kind", ["prabayar", "pascabayar", "dil"])
def test_condition_dropdown_changes_results_and_keeps_source_scope(
    page: Page, servers: tuple[str, str], kind: str
) -> None:
    content = "IDPEL,NAMA,LAT,LON\n001,Lengkap,-6.2,106.8\n002,Koordinat kosong,,\n003,Bermasalah,bad,106.8\n004,Lengkap lain,-6.3,106.9\n"
    older = upload(servers[1], kind, content)
    upload(servers[1], kind, content)
    page.goto(f"/master/{kind}")
    table = page.get_by_role("table")
    footer = page.get_by_label("Navigasi halaman master", exact=True)
    conditions = page.get_by_label("Status kelengkapan data", exact=True)
    expect(footer).to_contain_text("8 baris sesuai filter")
    for condition, total in [("invalid", 2), ("incomplete", 2), ("valid", 6), ("all", 8), ("incomplete", 2)]:
        conditions.select_option(condition)
        expect(footer).to_contain_text(f"{total} baris sesuai filter")
        expect(table.get_by_role("row")).to_have_count(total + 1)
    page.get_by_label("Berkas sumber", exact=True).select_option(str(older))
    expect(footer).to_contain_text("1 baris sesuai filter")
    expect(table).to_contain_text("Koordinat kosong")
    search = page.get_by_label("Cari data master", exact=True)
    search.fill("Bermasalah")
    expect(footer).to_contain_text("0 baris sesuai filter")
    conditions.select_option("invalid")
    expect(footer).to_contain_text("1 baris sesuai filter")
    expect(table).to_contain_text("Bermasalah")
    search.fill("")
    conditions.select_option("valid")
    expect(footer).to_contain_text("3 baris sesuai filter")
    conditions.select_option("all")
    expect(footer).to_contain_text("4 baris sesuai filter")
