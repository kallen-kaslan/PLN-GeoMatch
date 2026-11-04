"""Manual points follow categorized checks, map decisions, and the standard export."""

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from openpyxl import load_workbook
from playwright.sync_api import Page, Route, expect
from test_corrections_browser import launch, prepare


def fill_point(page: Page, idpel: str = "") -> None:
    page.goto("/process")
    page.get_by_label("Nama sesi", exact=True).fill('Survei, "Gardu A"')
    page.get_by_label("Referensi survei / ID titik", exact=True).fill('TITIK, "001"')
    page.get_by_label("IDPEL awal (opsional)", exact=True).fill(idpel)
    page.get_by_label("Nomor agenda (opsional)", exact=True).fill("000123")
    page.get_by_label("Latitude (Y)", exact=True).fill("-6,2")
    page.get_by_label("Longitude (X)", exact=True).fill("106,8")
    page.get_by_label("Radius pemeriksaan (meter)", exact=True).fill("10")


@pytest.mark.parametrize("idpel,kind,slug", [
    ("", "idpel_kosong", "idpel-kosong"),
    ("000777", "idpel_tidak_ketemu", "idpel-tidak-ketemu"),
])
def test_manual_point_check_map_choice_and_export(
    page: Page, servers: tuple[str, str], tmp_path: Path,
    idpel: str, kind: str, slug: str,
) -> None:
    api = servers[1]
    prepare(api, candidates=7)
    legacy_requests = []
    page.on("request", lambda request: legacy_requests.append(request.url)
            if "/process/run-matching" in request.url else None)
    fill_point(page, idpel)
    page.get_by_role("button", name="Simpan & Buka Data Koreksi", exact=True).click()
    page.wait_for_url(f"**/koreksi/{slug}?*")
    batch = int(parse_qs(urlparse(page.url).query)["batch_id"][0])
    expect(page.get_by_label("Radius pemeriksaan (meter)", exact=True)).to_have_value("10")
    rows = httpx.get(f"{api}/corrections/{kind}/records", params={"batch_id": batch}).json()
    assert rows["total"] == 1
    fields = rows["items"][0]["fields"]
    assert fields["survey_ref"] == 'TITIK, "001"'
    assert fields["agenda_ref"] == "000123"
    assert not fields.get("meter_ref")
    assert fields["lat"] == -6.2 and fields["lon"] == 106.8
    assert (fields.get("idpel") or "") == idpel
    launch(page)
    process = int(parse_qs(urlparse(page.url).query)["process_id"][0])
    stored = httpx.get(f"{api}/corrections/{kind}/records", params={"process_id": process}).json()["items"]
    assert len(stored) == 1 and stored[0]["candidate_count"] == 7
    assert not legacy_requests
    page.get_by_role("link", name="Buka Peta Koreksi", exact=True).click()
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    page.get_by_label("Petugas peta", exact=True).fill("Petugas Manual")
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    expect(page.get_by_role("region", name="Detail target terpilih", exact=True)).to_contain_text("Pilihan aktif: 002")
    page.get_by_role("link", name="Lihat Hasil Koreksi", exact=True).click()
    expect(page.get_by_role("region", name="Daftar hasil koreksi", exact=True)).to_contain_text("Petugas Manual")
    with page.expect_download() as download:
        page.get_by_role("button", name="Ekspor hasil XLSX", exact=True).click()
    path = tmp_path / "manual.xlsx"
    download.value.save_as(path)
    book = load_workbook(path)
    assert book.sheetnames == ["Hasil Koreksi"]
    values = list(book.active.values)
    assert len(values) == 2
    assert len(values[0]) == 9
    result = dict(zip(values[0], values[1]))
    assert result["noagenda"] == "000123"
    assert result["idpelanggan"] == "002"
    assert result["y_akhir"] == "-6.2" and result["x_akhir"] == "106.8"
    assert "verif" not in result and "x_acc" not in result and "y_acc" not in result
    book.close()
    page.reload()
    expect(page.get_by_role("region", name="Daftar hasil koreksi", exact=True)).to_contain_text("002")


def test_manual_mapping_retry_reuses_saved_point(
    page: Page, servers: tuple[str, str],
) -> None:
    uploads = []
    page.on("request", lambda request: uploads.append(request.url)
            if request.method == "POST" and request.url.endswith("/upload/") else None)
    attempts = 0

    def fail_once(route: Route) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            route.fulfill(status=503, json={"detail": "Validasi sementara tidak tersedia"})
        else:
            route.continue_()

    page.route("**/upload/confirm-mapping", fail_once)
    fill_point(page)
    save = page.get_by_role("button", name="Simpan & Buka Data Koreksi", exact=True)
    save.click()
    expect(page.get_by_role("alert")).to_have_text("Validasi sementara tidak tersedia")
    expect(save).to_be_enabled()
    save.click()
    page.wait_for_url("**/koreksi/idpel-kosong?*")
    assert attempts == 2 and len(uploads) == 1
    batches = httpx.get(servers[1] + "/corrections/idpel_kosong/batches").json()
    assert len(batches) == 1 and batches[0]["total_rows"] == 1


def test_manual_coordinates_validated_before_saving_on_mobile(
    page: Page, servers: tuple[str, str],
) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    fill_point(page)
    latitude = page.get_by_label("Latitude (Y)", exact=True)
    latitude.fill("91")
    page.get_by_role("button", name="Simpan & Buka Data Koreksi", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Latitude (Y) harus berupa angka")
    assert httpx.get(servers[1] + "/corrections/idpel_kosong/batches").json() == []
    latitude.fill("-6.2")
    page.get_by_label("Longitude (X)", exact=True).fill("NaN")
    page.get_by_role("button", name="Simpan & Buka Data Koreksi", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Longitude (X) harus berupa angka")
    assert httpx.get(servers[1] + "/corrections/idpel_kosong/batches").json() == []
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
