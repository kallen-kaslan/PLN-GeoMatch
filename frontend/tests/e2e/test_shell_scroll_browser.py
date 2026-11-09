"""Scrolling map details must not move or shorten the application frame."""

import pytest
from playwright.sync_api import expect
from test_correction_map_browser import setup_map


@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 1517, "height": 776},
        {"width": 1366, "height": 650},
        {"width": 390, "height": 844},
    ],
)
def test_map_scrolling_keeps_frame_full_height_and_all_content_reachable(
    page, servers, viewport
):
    page.set_viewport_size(viewport)
    setup_map(page, servers[1], count=2, stacked=False)
    if viewport["width"] < 1280:
        page.get_by_role("tab", name="Daftar", exact=True).click()
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("12 kandidat tersimpan")
    if viewport["width"] < 1280:
        page.get_by_role("tab", name="Detail", exact=True).click()
    candidates.get_by_role("article").last.evaluate(
        "element => element.scrollIntoView({ block: 'center' })"
    )
    frame = page.locator("#main-content").evaluate("""element => ({
        top: element.getBoundingClientRect().top,
        bottom: element.getBoundingClientRect().bottom,
        viewport: innerHeight, windowScroll: scrollY,
        documentHeight: document.documentElement.scrollHeight,
        scrollHeight: element.scrollHeight, clientHeight: element.clientHeight
    })""")
    assert frame["windowScroll"] == 0, frame
    assert abs(frame["bottom"] - frame["viewport"]) <= 1, frame
    assert frame["documentHeight"] <= frame["viewport"] + 1, frame
    assert frame["scrollHeight"] > frame["clientHeight"], frame
    if viewport["width"] >= 1024:
        sidebar = page.locator("#app-sidebar").bounding_box()
        assert (
            sidebar and abs(sidebar["y"] + sidebar["height"] - viewport["height"]) <= 1
        )
    expect(page.locator(".geo-topbar")).to_be_in_viewport()
    page.locator("#main-content").evaluate(
        "element => element.scrollTo({ top: 0, behavior: 'instant' })"
    )
    expect(
        page.get_by_role("heading", name="Peta Koreksi", exact=True)
    ).to_be_in_viewport()
    assert page.evaluate("scrollY") == 0
