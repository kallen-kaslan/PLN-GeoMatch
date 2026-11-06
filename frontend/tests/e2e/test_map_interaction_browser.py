"""Map selection preserves the user's zoom, viewport and page position."""
import re
import tempfile
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_correction_map_browser import setup_map


def capture_map(page):
    page.add_init_script("""
      let leaflet;
      Object.defineProperty(window, 'L', {
        configurable: true,
        get: () => leaflet,
        set(value) {
          leaflet = value;
          const create = value.map;
          value.map = (...args) => {
            const map = create(...args);
            window.__testMap = map;
            return map;
          };
        },
      });
    """)


def view(page):
    return page.evaluate("""() => ({
      zoom: window.__testMap.getZoom(),
      lat: window.__testMap.getCenter().lat,
      lng: window.__testMap.getCenter().lng,
      scroll: [document.scrollingElement.scrollTop, document.querySelector('main').scrollTop],
    })""")


@pytest.mark.parametrize("width", [1440, 390])
def test_mouse_selection_clear_and_keyboard_preserve_view(page, servers, width):
    page.set_viewport_size({"width": width, "height": 1000})
    capture_map(page)
    setup_map(page, servers[1], count=2, stacked=False)
    canvas = page.get_by_label("Peta target koreksi", exact=True)
    canvas.scroll_into_view_if_needed()
    page.evaluate("window.__testMap.setZoom(window.__testMap.getZoom() + 1, {animate: false})")
    before = view(page)
    expect(canvas.locator("path.geo-map-target")).to_have_count(2)
    expect(canvas.locator("path.geo-map-candidate")).to_have_count(0)
    expect(canvas.locator("path.geo-map-radius")).to_have_count(0)
    expect(page.get_by_label("Legenda peta", exact=True).locator("li")).to_have_text(["Data Koreksi", "Data Dipilih", "Kandidat"])
    point = page.get_by_role("button", name="Titik koreksi baris 2", exact=True)
    expect(point).to_have_attribute("fill", "#7f9fcd")
    point.hover()
    tooltip = page.locator(".geo-map-tooltip")
    expect(tooltip).to_contain_text("Objek ID: 0001")
    expect(tooltip).to_contain_text("Jumlah Kandidat: 12")
    expect(tooltip).not_to_contain_text("AGENDA")
    expect(tooltip).not_to_contain_text("Nomor Agenda")
    expect(tooltip).not_to_contain_text("Baris")
    expect(tooltip).not_to_contain_text("\u2014")
    box = tooltip.bounding_box()
    assert box is not None and 200 <= box["width"] <= 250
    assert box["height"] < 140
    page.screenshot(path=str(Path(tempfile.gettempdir()) / f"pln-map-tooltip-soft-{width}.png"))
    point.click()
    expect(page).to_have_url(re.compile(r"record_id="))
    expect(point).to_have_attribute("fill", "#e4a36d")
    expect(canvas.locator("path.geo-map-target")).to_have_count(1)
    expect(page.get_by_role("button", name="Titik koreksi baris 3", exact=True)).to_have_count(0)
    expect(canvas.locator("path.geo-map-radius")).to_be_visible()
    expect(page.get_by_role("region", name="Kandidat target peta", exact=True)).to_contain_text("12 kandidat tersimpan")
    selected = view(page)
    assert selected["zoom"] == before["zoom"]
    assert abs(selected["lat"] - (-6.2)) < 0.00001
    assert abs(selected["lng"] - 106.8) < 0.00001
    assert selected["scroll"] == before["scroll"]
    expect(canvas.locator('path[fill="#83b58b"]').first).to_be_visible()
    expect(page.get_by_label("Legenda peta", exact=True)).to_contain_text("Data Dipilih")
    expect(page.get_by_label("Legenda peta", exact=True)).to_contain_text("Kandidat")
    page.get_by_role("button", name="Lepas pilihan target", exact=True).click()
    expect(page.get_by_role("region", name="Detail target terpilih", exact=True)).to_have_count(0)
    expect(canvas).to_be_focused()
    assert view(page) == selected
    expect(canvas.locator("path.geo-map-target")).to_have_count(2)
    expect(canvas.locator("path.geo-map-candidate")).to_have_count(0)
    expect(canvas.locator("path.geo-map-radius")).to_have_count(0)
    expect(point).to_have_attribute("fill", "#7f9fcd")
    point.focus()
    point.press("Enter")
    expect(page.get_by_role("region", name="Detail target terpilih", exact=True)).to_contain_text("Target 1")
    assert view(page)["zoom"] == before["zoom"]
    if width < 1280:
        expect(page.get_by_role("tab", name="Peta", exact=True)).to_have_attribute("aria-selected", "true")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(Path(tempfile.gettempdir()) / f"pln-map-ui-{width}.png"))


def test_stacked_targets_popup_can_choose_a_source_row(page, servers):
    setup_map(page, servers[1], count=27)
    page.get_by_label("Peta target koreksi", exact=True).scroll_into_view_if_needed()
    point = page.get_by_role("button", name="27 target bertumpuk", exact=True)
    point.hover()
    tooltip = page.locator(".geo-map-tooltip")
    expect(tooltip).to_contain_text("27 data di lokasi ini")
    expect(tooltip).to_contain_text("Jumlah Kandidat: 12")
    expect(tooltip).to_contain_text("Objek ID: 0001")
    expect(tooltip).not_to_contain_text("AGENDA")
    expect(tooltip).not_to_contain_text("Baris")
    box = tooltip.bounding_box()
    assert box is not None and box["width"] >= 200 and box["height"] < 200
    point.click()
    popup = page.locator(".leaflet-popup-content")
    expect(popup).to_be_visible()
    popup.get_by_role("button").filter(has_text="Target 27").click()
    expect(page.get_by_role("region", name="Detail target terpilih", exact=True)).to_contain_text("Target 27")
    expect(page.locator("path.geo-map-target-active")).to_have_count(1)
    expect(page.get_by_role("button", name="27 target bertumpuk", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Titik koreksi baris 28", exact=True)).to_have_attribute("fill", "#e4a36d")
    expect(page.locator("path.geo-map-radius")).to_be_visible()
    expect(page.get_by_role("region", name="Kandidat target peta", exact=True)).to_contain_text("12 kandidat tersimpan")


def test_candidate_tooltip_and_popup_show_names_and_open_detail(page, servers):
    setup_map(page, servers[1], count=1)
    page.get_by_label("Peta target koreksi", exact=True).scroll_into_view_if_needed()
    page.get_by_role("button", name="Titik koreksi baris 2", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("12 kandidat tersimpan")
    marker = page.locator('.leaflet-overlay-pane path[fill="#83b58b"]')
    marker.hover()
    tooltip = page.locator(".geo-map-tooltip")
    expect(tooltip).to_contain_text("12 kandidat di lokasi ini")
    expect(tooltip).to_contain_text("Pelanggan 2")
    expect(tooltip).to_contain_text("IDPEL 002")
    expect(tooltip).not_to_contain_text("Pelanggan 13")
    marker.click()
    popup = page.locator(".leaflet-popup-content")
    expect(popup).to_contain_text("Jarak 0 m")
    popup.get_by_role("button").filter(has_text="Pelanggan 13").click()
    expect(candidates.get_by_role("article", name="Kandidat peta 12", exact=True)).to_be_focused()
