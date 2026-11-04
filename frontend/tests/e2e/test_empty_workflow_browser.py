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
    expect(table.get_by_role("columnheader")).to_have_text(["No", "Nomor agenda", "Nama pelanggan", "Koordinat X", "Koordinat Y", "Status", "Kandidat", "Aksi"])
    row = table.get_by_role("row").filter(has_text="Pelanggan A")
    expect(row).to_contain_text("Kandidat ditemukan")
    row.get_by_role("button", name="Detail", exact=True).click()
    detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
    expect(detail.get_by_role("heading", name="Kandidat tersimpan (1)", exact=True)).to_be_visible()
    expect(detail.get_by_role("article").get_by_text("#1 \u00b7 002", exact=True)).to_be_visible()
    expect(detail.get_by_role("article").get_by_text("001", exact=True)).to_have_count(0)



def test_overview_loads_without_batch_list_and_syncs_new_upload(page: Page, servers: tuple[str, str]) -> None:
    from test_corrections_browser import upload

    page.route("**/corrections/idpel_kosong/batches", lambda route: route.abort())
    page.goto("/koreksi/idpel-kosong")
    summary = page.get_by_role("region", name="Ringkasan IDPEL Kosong", exact=True)
    total = summary.get_by_text("Total data", exact=True).locator("..")
    expect(total).to_contain_text("0")
    upload(servers[1], "idpel_kosong", "noagenda,latitudey,longitude\nNEW-LIVE,-6.2,106.8\n")
    expect(total).to_contain_text("1", timeout=12000)
    expect(summary.get_by_text("Belum diproses", exact=True).locator("..")).to_contain_text("1", timeout=12000)
    expect(page.get_by_role("cell", name="NEW-LIVE", exact=True)).to_be_visible(timeout=12000)
