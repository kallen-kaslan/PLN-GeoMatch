"""Sidebar brand, active-page title and account remain usable across viewports."""
from pathlib import Path

from playwright.sync_api import Page, expect


def test_desktop_brand_collapse_and_active_submenu_title(page: Page, tmp_path: Path) -> None:
    page.goto("/")
    sidebar = page.locator("#app-sidebar")
    topbar = page.locator(".geo-topbar")
    expect(sidebar.get_by_text("PLN GeoMatch", exact=True)).to_be_visible()
    expect(topbar.get_by_label("Halaman aktif", exact=True)).to_have_text("Dashboard")
    assert "PLN GeoMatch" not in topbar.inner_text()
    sidebar.get_by_role("link", name="IDPEL Kosong", exact=True).click()
    expect(topbar.get_by_label("Halaman aktif", exact=True)).to_have_text("IDPEL Kosong")
    expect(topbar.get_by_role("navigation", name="Jejak halaman")).to_have_count(0)
    page.get_by_role("link", name="Unggah data", exact=True).click()
    breadcrumb = topbar.get_by_role("navigation", name="Jejak halaman", exact=True)
    expect(breadcrumb.get_by_role("link", name="IDPEL Kosong", exact=True)).to_have_attribute("href", "/koreksi/idpel-kosong")
    expect(breadcrumb.get_by_label("Halaman aktif", exact=True)).to_have_text("Unggah Data")
    back = page.get_by_role("link", name="Kembali ke IDPEL Kosong", exact=True)
    expect(back).to_be_visible()
    expect(back).to_have_text("")
    assert back.bounding_box()["width"] >= 44
    assert topbar.bounding_box()["height"] >= 72
    page.screenshot(path=str(tmp_path / "upload-header.png"))
    print("UI_SCREENSHOT", tmp_path / "upload-header.png")
    back.click()
    expect(topbar.get_by_role("navigation", name="Jejak halaman")).to_have_count(0)
    page.get_by_role("link", name="Unggah data", exact=True).click()
    title = topbar.get_by_label("Judul fitur", exact=True)
    expect(title).to_have_text("IDPEL Kosong")
    title_box, breadcrumb_box = title.bounding_box(), breadcrumb.bounding_box()
    assert title_box and breadcrumb_box
    assert title_box["y"] + title_box["height"] <= breadcrumb_box["y"]
    page.reload()
    expect(breadcrumb.get_by_label("Halaman aktif", exact=True)).to_have_text("Unggah Data")
    breadcrumb.get_by_role("link", name="IDPEL Kosong", exact=True).click()
    expect(topbar.get_by_role("navigation", name="Jejak halaman")).to_have_count(0)
    expect(topbar.get_by_label("Halaman aktif", exact=True)).to_have_text("IDPEL Kosong")
    side_box, bar_box = sidebar.bounding_box(), topbar.bounding_box()
    assert side_box and bar_box
    assert side_box["x"] + side_box["width"] <= bar_box["x"]
    assert side_box["y"] == bar_box["y"]
    page.screenshot(path=str(tmp_path / "layout-expanded.png"))
    print("UI_SCREENSHOT", tmp_path / "layout-expanded.png")
    topbar.get_by_role("button", name="Perkecil Sidebar", exact=True).click()
    expect(sidebar.get_by_text("PLN GeoMatch", exact=True)).to_have_count(0)
    expect(sidebar.get_by_role("link", name="PLN GeoMatch ? Dashboard", exact=True)).to_be_visible()
    assert sidebar.bounding_box()["width"] == 64
    page.reload()
    expect(topbar.get_by_role("button", name="Perluas Sidebar", exact=True)).to_be_visible()
    topbar.get_by_role("button", name="Perluas Sidebar", exact=True).click()
    sidebar.get_by_role("link", name="Pascabayar", exact=True).click()
    expect(topbar.get_by_label("Halaman aktif", exact=True)).to_have_text("Pascabayar")
    topbar.get_by_role("button", name="Menu akun pengguna", exact=True).click()
    expect(page.get_by_role("menuitem", name="Keluar dari Sistem")).to_be_visible()
    page.keyboard.press("Escape")
    expect(topbar.get_by_role("button", name="Menu akun pengguna", exact=True)).to_be_focused()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_mobile_title_brand_drawer_and_navigation(page: Page, tmp_path: Path) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/koreksi/idpel-kosong?flow=upload")
    topbar = page.locator(".geo-topbar")
    expect(topbar.get_by_label("Halaman aktif", exact=True)).to_have_text("Unggah Data")
    expect(topbar.get_by_label("Judul fitur", exact=True)).to_have_text("IDPEL Kosong")
    page.screenshot(path=str(tmp_path / "breadcrumb-mobile.png"))
    print("UI_SCREENSHOT", tmp_path / "breadcrumb-mobile.png")
    breadcrumb = topbar.get_by_role("navigation", name="Jejak halaman", exact=True)
    expect(breadcrumb.get_by_role("link", name="IDPEL Kosong", exact=True)).to_be_visible()
    title_box = breadcrumb.bounding_box()
    account_box = topbar.get_by_role("button", name="Menu akun pengguna", exact=True).bounding_box()
    assert title_box and account_box
    assert title_box["x"] + title_box["width"] <= account_box["x"]
    expect(topbar.get_by_role("button", name="Menu akun pengguna", exact=True)).to_be_visible()
    topbar.get_by_role("button", name="Buka menu navigasi", exact=True).click()
    drawer = page.get_by_role("dialog", name="Menu Navigasi Mobile", exact=True)
    expect(drawer.get_by_text("PLN GeoMatch", exact=True)).to_be_visible()
    drawer.get_by_role("link", name="IDPEL Tidak Ketemu", exact=True).click()
    expect(drawer).not_to_be_visible()
    expect(topbar.get_by_label("Halaman aktif", exact=True)).to_have_text("IDPEL Tidak Ketemu")
    page.screenshot(path=str(tmp_path / "layout-mobile.png"))
    print("UI_SCREENSHOT", tmp_path / "layout-mobile.png")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
