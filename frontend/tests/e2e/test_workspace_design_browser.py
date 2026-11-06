"""Operational layouts preserve source values, focus, context, and map interactions."""

from pathlib import Path

import httpx
from playwright.sync_api import Page, expect
from test_correction_map_browser import setup_map
from test_corrections_browser import upload


def test_pdpj_drawer_keeps_table_position_source_values_and_keyboard_focus(
    page: Page, servers: tuple[str, str], tmp_path: Path,
) -> None:
    api = servers[1]
    upload(api, "dil", "IDPEL,NAMA,LAT,LON\n001,Pelanggan Uji,-6.20000001,106.80000001\n")
    batch = upload(api, "pdpj", "IDPEL,NAMA,LAT,LON\n001,Pelanggan Uji,-6.20000001,106.80000001\n")
    review = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": batch}).json()
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(f"/pdpj?batch_id={batch}&review_id={review['id']}")
    trigger = page.get_by_role("button", name="Detail PDPJ baris 2", exact=True)
    expect(trigger).to_be_visible()
    trigger.scroll_into_view_if_needed()
    position = page.locator("#main-content").evaluate("element => element.scrollTop")
    trigger.click()
    drawer = page.get_by_role("dialog", name="Panel pemeriksaan PDPJ", exact=True)
    expect(drawer).to_be_visible()
    expect(drawer.get_by_role("region", name="Detail pemeriksaan PDPJ")).to_contain_text("106.80000001")
    expect(drawer).to_contain_text("-6.20000001")
    assert drawer.evaluate("element => element.contains(document.activeElement)")
    page.screenshot(path=str(tmp_path / "pdpj-drawer.png"))
    page.keyboard.press("Escape")
    expect(drawer).to_have_count(0)
    expect(trigger).to_be_focused()
    assert page.locator("#main-content").evaluate("element => element.scrollTop") == position
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#main-content").evaluate("element => element.scrollTop = 0")
    page.screenshot(path=str(tmp_path / "pdpj-desktop.png"))
    print("UI_SCREENSHOT", tmp_path / "pdpj-desktop.png")
    print("UI_SCREENSHOT", tmp_path / "pdpj-drawer.png")


def test_desktop_map_and_candidate_inspector_share_the_work_area(
    page: Page, servers: tuple[str, str], tmp_path: Path,
) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})
    setup_map(page, servers[1], count=2, stacked=False)
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    expect(page.get_by_label("Petugas peta", exact=True)).to_have_value("test-admin")

    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates.get_by_role("article")).to_have_count(10)
    map_box = page.get_by_label("Peta target koreksi", exact=True).bounding_box()
    inspector = page.get_by_role("complementary", name="Inspeksi target dan kandidat", exact=True).bounding_box()
    assert map_box and inspector
    assert map_box["x"] + map_box["width"] <= inspector["x"]
    assert inspector["width"] >= 350
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    expect(page.get_by_role("region", name="Detail target terpilih")).to_contain_text("Pilihan aktif: 002")
    page.get_by_role("region", name="Pemetaan koreksi", exact=True).scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path / "map-desktop.png"))
    print("UI_SCREENSHOT", tmp_path / "map-desktop.png")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_mobile_map_navigation_and_drawer_remain_usable(
    page: Page, servers: tuple[str, str], tmp_path: Path,
) -> None:
    setup_map(page, servers[1], count=2, stacked=False)
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("tab", name="Daftar", exact=True).click()
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    expect(page.get_by_role("tab", name="Peta", exact=True)).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("region", name="Detail target terpilih")).to_be_visible()
    expect(page.get_by_label("Peta target koreksi", exact=True)).to_be_visible()
    expect(page.get_by_role("region", name="Kandidat target peta", exact=True)).to_contain_text("12 kandidat tersimpan")
    page.reload()
    expect(page.get_by_role("tab", name="Peta", exact=True)).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("region", name="Detail target terpilih")).to_contain_text("Target baris 2")
    page.get_by_role("tab", name="Detail", exact=True).click()
    expect(page.get_by_role("region", name="Detail target terpilih")).to_be_visible()
    expect(page.get_by_role("region", name="Kandidat target peta", exact=True)).to_contain_text("12 kandidat tersimpan")
    page.get_by_role("tab", name="Peta", exact=True).click()
    expect(page.get_by_label("Peta target koreksi", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.get_by_role("button", name="Buka menu navigasi", exact=True).click()
    navigation = page.get_by_role("dialog", name="Menu Navigasi Mobile", exact=True)
    expect(navigation).to_be_visible()
    page.keyboard.press("Escape")
    expect(navigation).not_to_be_visible()
    page.get_by_role("button", name="Buka menu navigasi", exact=True).click()
    page.set_viewport_size({"width": 1440, "height": 900})
    expect(navigation).not_to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("tab", name="Peta", exact=True).scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path / "map-mobile.png"))
    print("UI_SCREENSHOT", tmp_path / "map-mobile.png")
    page.get_by_role("button", name="Lepas pilihan target", exact=True).click()
    expect(page.get_by_role("tab", name="Daftar", exact=True)).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("region", name="Kandidat target peta", exact=True)).to_have_count(0)
    expect(page.get_by_role("region", name="Detail target terpilih", exact=True)).to_have_count(0)
    expect(page.get_by_role("heading", name="Target IDPEL Kosong", exact=True)).to_be_focused()
    page.get_by_role("button", name="Pilih target baris 3", exact=True).click()
    expect(page.get_by_role("tab", name="Peta", exact=True)).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("region", name="Kandidat target peta", exact=True)).to_contain_text("1 kandidat tersimpan")
