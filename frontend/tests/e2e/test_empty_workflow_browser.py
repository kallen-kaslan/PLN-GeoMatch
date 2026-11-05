"""Two-step empty-ID workflow against temporary test servers and SQLite only."""
import io
from pathlib import Path

from openpyxl import Workbook
from playwright.sync_api import Page, expect
from test_corrections_browser import prepare


def test_empty_home_and_mobile_navigation_have_no_error_state(page: Page) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/koreksi/idpel-kosong")
    expect(page.get_by_text("Belum ada data. Klik Unggah data untuk memulai.", exact=True)).to_be_visible()
    expect(page.get_by_role("region", name="Proses IDPEL Kosong belum selesai", exact=True)).to_have_count(0)
    expect(page.get_by_role("alert")).to_have_count(0)
    page.get_by_role("button", name="Buka menu navigasi", exact=True).click()
    drawer = page.get_by_role("dialog", name="Menu Navigasi Mobile", exact=True)
    expect(drawer).to_be_visible()
    page.keyboard.press("Escape")
    expect(drawer).not_to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_upload_resume_analysis_recommendation_search_and_stored_candidates(
    page: Page, servers: tuple[str, str], tmp_path: Path,
) -> None:
    prepare(servers[1], candidates=1)
    book = Workbook()
    sheet = book.active
    sheet.title = "Kosong"
    sheet.append(["noagenda", "idpelanggan", "namapelanggan", "nokwhmeter", "latitudey", "longitude"])
    sheet.append(["000001", None, "Pelanggan A", "M1", -6.2, 106.8])
    sheet.append(["000002", None, "Pelanggan B", "M2", -6.2, 106.8])
    sheet.append(["000003", None, "Koordinat rusak", None, 95, 106.8])
    book.create_sheet("Lain")
    data = io.BytesIO()
    book.save(data)
    page.goto("/koreksi/idpel-kosong")
    page.get_by_role("link", name="Unggah data", exact=True).click()
    page.get_by_label("Berkas IDPEL Kosong", exact=True).set_input_files({
        "name": "idpel-kosong-uji.xlsx",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "buffer": data.getvalue(),
    })
    expect(page.get_by_role("heading", name="Unggah Data", exact=True)).to_be_visible()
    expect(page.get_by_label("Pilih sheet atau tabel", exact=True)).to_be_visible()
    expect(page.get_by_role("table", name="Tabel asli", exact=True)).to_have_count(0)
    page.get_by_label("Pilih sheet atau tabel", exact=True).select_option("Kosong")
    raw = page.get_by_role("table", name="Tabel asli", exact=True)
    expect(raw.get_by_role("columnheader")).to_have_text(["noagenda", "idpelanggan", "namapelanggan", "nokwhmeter", "latitudey", "longitude"])
    expect(raw.get_by_role("cell", name="000001", exact=True)).to_be_visible()
    expect(page.locator(".geo-topbar").get_by_label("Halaman aktif", exact=True)).to_have_text("Unggah Data")
    page.get_by_role("button", name="Simpan dan berikutnya", exact=True).click()
    expect(page.locator(".geo-topbar").get_by_label("Halaman aktif", exact=True)).to_have_text("Unggah Data")
    expect(page.locator(".geo-topbar").get_by_role("link", name="IDPEL Kosong", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Analisis radius", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Lihat hasil", exact=True)).to_be_disabled()
    page.get_by_role("link", name="Kembali ke IDPEL Kosong", exact=True).click()
    pending = page.get_by_role("region", name="Proses IDPEL Kosong belum selesai", exact=True)
    expect(pending).to_contain_text("Menunggu langkah berikutnya")
    expect(pending).to_contain_text("3 baris sudah disimpan; 0 baris telah dianalisis")
    card = pending.get_by_role("article")
    expect(card).to_have_count(1)
    card_box, region_box = card.bounding_box(), pending.bounding_box()
    assert card_box and region_box
    assert abs(card_box["width"] - region_box["width"]) <= 2
    assert card_box["height"] < 160
    page.screenshot(path=str(tmp_path / "pending-work-layout.png"))
    print("UI_SCREENSHOT", tmp_path / "pending-work-layout.png")
    pending.get_by_role("link", name="Lanjutkan proses", exact=True).click()
    page.reload()
    page.get_by_role("button", name="Mulai analisis", exact=True).click()
    expect(page.get_by_text("Analisis selesai", exact=True)).to_be_visible(timeout=20000)
    radius = page.get_by_label("Radius pencarian", exact=True)
    expect(radius).to_have_value("5")
    page.get_by_role("link", name="Kembali ke IDPEL Kosong", exact=True).click()
    expect(pending).to_contain_text("Analisis selesai")
    pending.get_by_role("link", name="Lanjutkan proses", exact=True).click()
    expect(radius).to_have_value("5")
    radius.fill("0")
    expect(page.get_by_role("button", name="Mulai pencarian kandidat", exact=True)).to_be_disabled()
    radius.fill("5")
    page.get_by_role("button", name="Mulai pencarian kandidat", exact=True).click()
    results = page.get_by_role("button", name="Lihat hasil", exact=True)
    expect(results).to_be_enabled(timeout=20000)
    search = page.get_by_role("region", name="Pencarian kandidat", exact=True)
    expect(search.get_by_text("Kandidat ditemukan", exact=True).locator("..")).to_contain_text("2")
    expect(search.get_by_text("Koordinat bermasalah", exact=True).locator("..")).to_contain_text("1")
    page.reload()
    expect(radius).to_have_value("5")
    expect(radius).to_be_disabled()
    expect(results).to_be_enabled()
    coverage = page.get_by_role("heading", name="Perkiraan cakupan", exact=True).locator("..")
    expect(coverage.get_by_role("definition")).to_have_text(["2", "0", "1"])
    page.screenshot(path=str(tmp_path / "empty-workflow-completed.png"), full_page=True)
    print("UI_SCREENSHOT", tmp_path / "empty-workflow-completed.png")
    results.click()
    expect(pending).to_have_count(0)
    table = page.get_by_role("table")
    expect(table.get_by_role("columnheader")).to_have_text(["No", "Objek ID", "Nomor agenda", "Nama pelanggan", "Koordinat X", "Koordinat Y", "Status", "Kandidat", "Aksi"])
    row = table.get_by_role("row").filter(has_text="Pelanggan A")
    expect(row).to_contain_text("Kandidat ditemukan")
    row.get_by_role("link", name="Detail", exact=True).click()
    expect(page.locator(".geo-topbar").get_by_label("Halaman aktif", exact=True)).to_have_text("Detail Data")
    expect(page.get_by_role("region", name="Data pelanggan", exact=True)).to_contain_text("Pelanggan A")
    detail = page.get_by_role("region", name="Daftar kandidat", exact=True)
    expect(detail.get_by_role("columnheader")).to_have_text(["No", "IDPEL", "Nama Pelanggan", "Nomor Agenda", "Koordinat X", "Koordinat Y", "Jarak", "Aksi"])
    expect(detail.get_by_role("cell", name="002", exact=True)).to_be_visible()
    expect(detail.get_by_role("cell", name="001", exact=True)).to_have_count(0)
    detail.get_by_role("button", name="Detail sumber kandidat 002", exact=True).click()
    popup = page.get_by_role("dialog", name="Detail Sumber Kandidat", exact=True)
    expect(popup).to_be_visible()
    expect(popup.get_by_role("heading", name="dil.csv", exact=True)).to_be_visible()
    expect(popup).to_contain_text("Sheet")
    popup.get_by_role("heading", name="Detail Sumber Kandidat", exact=True).click()
    expect(popup).to_be_visible()
    page.mouse.click(4, 4)
    expect(popup).to_have_count(0)
    detail.get_by_role("button", name="Detail sumber kandidat 002", exact=True).click()
    expect(popup).to_be_visible()
    page.keyboard.press("Escape")
    expect(popup).to_have_count(0)
    expect(detail.get_by_text("Versi", exact=False)).to_have_count(0)
    expect(detail.get_by_role("row").nth(1).get_by_role("cell").first).to_have_text("1")
    page.reload()
    expect(detail.get_by_role("cell", name="002", exact=True)).to_be_visible()
    page.locator(".geo-topbar").get_by_role("link", name="IDPEL Kosong", exact=True).click()
    expect(page.get_by_role("region", name="Ringkasan IDPEL Kosong", exact=True)).to_be_visible()




def test_overview_loads_without_batch_list_and_syncs_new_upload(page: Page, servers: tuple[str, str]) -> None:
    from test_corrections_browser import upload

    page.route("**/corrections/idpel_kosong/batches", lambda route: route.abort())
    page.goto("/koreksi/idpel-kosong")
    summary = page.get_by_role("region", name="Ringkasan IDPEL Kosong", exact=True)
    total = summary.get_by_text("Total Data", exact=True).locator("..")
    expect(total).to_contain_text("0")
    upload(servers[1], "idpel_kosong", "noagenda,latitudey,longitude\nNEW-LIVE,-6.2,106.8\n")
    expect(total).to_contain_text("1", timeout=12000)
    expect(summary.get_by_text("Belum Diproses", exact=True).locator("..")).to_contain_text("1", timeout=12000)
    expect(page.get_by_role("cell", name="NEW-LIVE", exact=True)).to_be_visible(timeout=12000)


def test_candidate_pagination_sizes_navigation_and_card_spacing(page: Page) -> None:
    """Synthetic API data verifies page controls without changing user data."""
    from urllib.parse import parse_qs, urlparse

    candidates = [{"id": index, "rank": index, "distance_meters": index * 1.5,
                   "fields": {"idpel": f"{index:012}", "nama": f"Kandidat {index}",
                              "agenda_ref": f"A{index}", "lat": -6.2, "lon": 106.8},
                   "observations": [], "is_accepted": 0} for index in range(1, 13)]

    def respond(route):
        params = parse_qs(urlparse(route.request.url).query)
        skip = int(params.get("skip", [0])[0])
        limit = int(params.get("limit", [10])[0])
        ordered = list(reversed(candidates)) if params.get("sort_order") == ["farthest"] else candidates
        route.fulfill(json={"id": 1, "batch_id": 1, "row_number": 1,
                            "filename": "contoh.csv", "source_sheet": "Data",
                            "raw_data": {"objectid": "132", "namapelanggan": "Contoh"},
                            "fields": {}, "search_status": "matched", "generation": 1,
                            "radius_meters": 235, "candidates_total": len(candidates),
                            "candidates": ordered[skip:skip + limit]})

    page.route("**/corrections/idpel_kosong/records/1?*", respond)
    page.goto("/koreksi/idpel-kosong?detail_record_id=1&batch_id=1&process_id=1&generation=1")
    section = page.get_by_role("region", name="Daftar kandidat", exact=True)
    table = section.get_by_role("table")
    expect(table.get_by_role("row")).to_have_count(11)
    size = section.get_by_label("Kandidat per halaman", exact=True)
    size.select_option("5")
    expect(table.get_by_role("row")).to_have_count(6)
    section.get_by_role("button", name="Halaman kandidat berikutnya", exact=True).click()
    expect(table.get_by_role("row").nth(1).get_by_role("cell").first).to_have_text("6")
    section.get_by_role("button", name="Halaman kandidat sebelumnya", exact=True).click()
    expect(table.get_by_role("row").nth(1).get_by_role("cell").first).to_have_text("1")
    expect(section.get_by_role("link", name="Buka peta", exact=True)).to_have_count(0)
    jump = section.get_by_role("spinbutton", name="Nomor halaman kandidat", exact=True)
    jump.fill("4")
    section.get_by_role("button", name="Buka", exact=True).click()
    assert not jump.evaluate("element => element.validity.valid")
    expect(table.get_by_role("row").nth(1).get_by_role("cell").first).to_have_text("1")
    jump.fill("3")
    jump.press("Enter")
    expect(table.get_by_role("row").nth(1).get_by_role("cell").first).to_have_text("11")
    expect(section.get_by_role("button", name="Halaman kandidat berikutnya", exact=True)).to_be_disabled()
    size.select_option("25")
    expect(table.get_by_role("row")).to_have_count(13)
    expect(table.get_by_role("row").nth(1).get_by_role("cell").first).to_have_text("1")
    order = section.get_by_label("Urutan jarak kandidat", exact=True)
    size.select_option("5")
    section.get_by_role("button", name="Halaman kandidat berikutnya", exact=True).click()
    expect(table.get_by_role("row").nth(1).get_by_role("cell").first).to_have_text("6")
    order.click()
    expect(order).to_have_attribute("aria-pressed", "true")
    expect(table.get_by_role("row").nth(1).get_by_role("cell").nth(1)).to_have_text("000000000012")
    expect(table.get_by_role("row").nth(1).get_by_role("cell").first).to_have_text("1")
    section.get_by_role("button", name="Halaman kandidat berikutnya", exact=True).click()
    expect(table.get_by_role("row").nth(1).get_by_role("cell").nth(1)).to_have_text("000000000007")
    order.click()
    expect(order).to_have_attribute("aria-pressed", "false")
    expect(table.get_by_role("row").nth(1).get_by_role("cell").nth(1)).to_have_text("000000000001")
    assert order.locator("xpath=../..").evaluate("element => element.tagName") == "HEADER"
    assert order.get_attribute("title") is None
    order.hover()
    expect(section.get_by_role("tooltip")).to_be_visible()
    expect(section.get_by_role("combobox", name="Urutan jarak kandidat", exact=True)).to_have_count(0)
    outer = section.bounding_box()
    inner = table.bounding_box()
    assert outer and inner and inner["x"] - outer["x"] >= 16
    page.set_viewport_size({"width": 390, "height": 844})
    expect(size).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
