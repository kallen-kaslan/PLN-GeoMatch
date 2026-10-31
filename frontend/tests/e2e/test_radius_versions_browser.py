"""Historical radius views and XLSX downloads stay on the selected search version."""

from pathlib import Path

import httpx
import pytest
from openpyxl import load_workbook
from playwright.sync_api import Page, expect
from test_correction_map_browser import setup_map


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_radius_dropdown_historical_choices_and_versioned_xlsx(
    page: Page, servers: tuple[str, str], tmp_path: Path, kind: str
) -> None:
    batch, process = setup_map(page, servers[1], kind=kind, count=2)
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    page.get_by_label("Petugas peta", exact=True).fill("Petugas Radius")
    page.get_by_role("button", name="Tampilkan kandidat target", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    detail = page.get_by_role("region", name="Detail target terpilih", exact=True)
    expect(detail).to_contain_text("Pilihan aktif: 002")
    page.get_by_label("Radius perluasan (meter)", exact=True).fill("100")
    page.get_by_role(
        "button", name="Perluas pemeriksaan dan tampilkan kandidat", exact=True
    ).click()
    expect(candidates).to_contain_text("13 kandidat tersimpan", timeout=30000)
    expect(
        page.get_by_role("region", name="Progres pemeriksaan koreksi")
    ).to_have_count(0)
    page.get_by_label("Alasan perubahan pilihan", exact=True).fill(
        "Bukti kandidat kedua sesuai"
    )
    candidates.get_by_role("button", name="Pilih kandidat 2", exact=True).click()
    expect(detail).to_contain_text("Pilihan aktif: 003")
    versions = page.get_by_label("Versi radius pemeriksaan", exact=True)
    expect(versions).to_have_value("2")
    expect(versions).to_contain_text("10 m · Versi 1 · Selesai")
    expect(versions).to_contain_text("100 m · Versi 2 · Selesai")
    versions.select_option("1")
    summary = page.get_by_role("region", name="Ringkasan radius peta", exact=True)
    expect(summary).to_contain_text("Radius 10 m · Versi 1")
    expect(page.get_by_label("Radius peta (meter)", exact=True)).to_have_value("10")
    radius = page.get_by_label("Radius peta (meter)", exact=True)
    expect(radius).to_be_enabled()
    expect(radius).to_have_attribute("max", "10")
    radius.fill("100")
    expect(radius).to_have_value("10")
    expect(page.get_by_label("Radius perluasan (meter)", exact=True)).to_be_disabled()
    radius.fill("1")
    expect(summary).to_contain_text("Radius 1 m · Versi 1")
    radius.fill("10")
    expect(summary).to_contain_text("Radius 10 m · Versi 1")
    expect(detail).to_contain_text("Pilihan aktif: 002")
    expect(
        detail.get_by_role("button", name="Batalkan pilihan", exact=True)
    ).to_be_disabled()
    page.get_by_role("button", name="Tampilkan kandidat target", exact=True).click()
    expect(candidates).to_contain_text("12 kandidat tersimpan")

    def verify_download(
        button: str, radius: int, version: int, identity: str, history: bool = False
    ) -> None:
        with page.expect_download() as downloaded:
            page.get_by_role("button", name=button, exact=True).click()
        assert downloaded.value.suggested_filename.endswith(
            f"radius_{radius}m_v{version}.xlsx"
        )
        target = tmp_path / f"{radius}-{version}-{history}-{button[:5]}.xlsx"
        downloaded.value.save_as(target)
        book = load_workbook(target)
        info = dict(list(book["Informasi"].values)[1:])
        assert info["Radius pemeriksaan (meter)"] == radius
        assert info["Versi pemeriksaan"] == version
        sheet = book["Riwayat Pilihan" if history else "Hasil Koreksi"]
        assert sheet["B2"].value == identity
        assert sheet["A1"].fill.patternType is None and sheet.freeze_panes is None
        if not history:
            report = list(book["Pemeriksaan Radius"].values)
            row = dict(zip(report[0], report[1]))
            assert row["radius_meter"] == radius and row["versi_pemeriksaan"] == version
        book.close()

    verify_download("Unduh hasil radius 10 m XLSX", 10, 1, "002")
    page.reload()
    expect(versions).to_have_value("1")
    expect(summary).to_contain_text("Radius 10 m · Versi 1")
    page.get_by_role("link", name="Lihat Hasil Koreksi", exact=True).click()
    results = page.get_by_role("region", name="Daftar hasil koreksi", exact=True)
    expect(page.get_by_label("Versi radius hasil koreksi", exact=True)).to_have_value(
        "1"
    )
    expect(results).to_contain_text("002")
    verify_download("Ekspor hasil XLSX", 10, 1, "002")
    page.get_by_role("link", name="Buka Riwayat Proses", exact=True).click()
    audit = page.get_by_role("region", name="Riwayat keputusan koreksi", exact=True)
    expect(audit).to_contain_text("Kandidat dipilih: 002")
    expect(audit).not_to_contain_text("Kandidat dipilih: 003")
    verify_download("Unduh riwayat XLSX", 10, 1, "002", history=True)
    page.goto(f"/result?category={kind}&process_id={process}&generation=2")
    expect(page.get_by_label("Versi radius hasil koreksi", exact=True)).to_have_value(
        "2"
    )
    expect(results).to_contain_text("003")
    verify_download("Ekspor hasil XLSX", 100, 2, "003")
    assert (
        len(
            httpx.get(f"{servers[1]}/corrections/{kind}/checks/{process}").json()[
                "runs"
            ]
        )
        == 2
    )
    page.goto(f"/peta-koreksi?category={kind}&batch_id={batch}&process_id={process}")
    expect(versions).to_have_value("2")
    expect(summary).to_contain_text("Radius 100 m · Versi 2")
    radius = page.get_by_label("Radius peta (meter)", exact=True)
    expect(radius).to_have_attribute("max", "100")
    radius.fill("101")
    expect(radius).to_have_value("100")
    expect(page.get_by_role("alert")).to_contain_text("Filter radius maksimal 100 m")
    page.goto(
        f"/peta-koreksi?category={kind}&batch_id={batch}&process_id={process}&generation=1&radius_meters=999"
    )
    expect(radius).to_have_value("10")
    expect(summary).to_contain_text("Radius 10 m · Versi 1")
    expect(page.get_by_role("alert")).to_contain_text(
        "Filter radius dibatasi maksimal 10 m"
    )
    expect(
        page.get_by_role("region", name="Progres pemeriksaan koreksi")
    ).to_have_count(0)
