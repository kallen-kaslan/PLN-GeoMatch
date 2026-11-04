"""Loading feedback and consistent dismissal of inspection drawers."""

import httpx
from playwright.sync_api import Page, Route, expect

from test_corrections_browser import prepare


def test_master_drawer_closes_outside_and_restores_focus(
    page: Page, servers: tuple[str, str]
) -> None:
    prepare(servers[1], candidates=1)
    page.goto("/master/dil")
    trigger = page.get_by_role("button", name="Lihat detail baris 2", exact=True)
    trigger.click()
    drawer = page.get_by_role("dialog", name="Detail sumber pelanggan", exact=True)
    expect(drawer).to_contain_text("Data asli berkas")
    drawer.get_by_role("heading", name="Detail sumber pelanggan", exact=True).click()
    expect(drawer).to_be_visible()
    # A selection that starts inside and ends outside must not dismiss the drawer.
    bounds = drawer.bounding_box()
    assert bounds is not None
    page.mouse.move(bounds["x"] + 20, 200)
    page.mouse.down()
    page.mouse.move(20, 200)
    page.mouse.up()
    expect(drawer).to_be_visible()
    page.mouse.click(20, 200)
    expect(drawer).to_have_count(0)
    expect(trigger).to_be_focused()
    assert page.evaluate("document.body.style.overflow") != "hidden"
    trigger.click()
    page.keyboard.press("Escape")
    expect(drawer).to_have_count(0)


def test_pdpj_loading_feedback_and_drawer_dismissal(
    page: Page, servers: tuple[str, str]
) -> None:
    review_id = prepare(servers[1], candidates=1)
    review = httpx.get(f"{servers[1]}/pdpj/reviews/{review_id}").json()
    observed = []

    def hold_batches(route: Route) -> None:
        response = route.fetch()
        loading = page.get_by_role("status").filter(has_text="Memuat daftar berkas PDPJ...")
        expect(loading).to_be_visible()
        expect(loading.locator("svg.animate-spin")).to_be_visible()
        expect(loading).to_contain_text("Mohon tunggu, data sedang dimuat.")
        observed.append(True)
        route.fulfill(response=response)

    page.route("**/api/pdpj/batches", hold_batches)
    with page.expect_response("**/api/pdpj/batches"):
        page.goto(f"/pdpj?batch_id={review['batch_id']}&review_id={review_id}")
    trigger = page.get_by_role("button", name="Detail PDPJ baris 2", exact=True)
    expect(trigger).to_be_enabled()
    assert observed
    expect(page.get_by_text("Mohon tunggu, data sedang dimuat.", exact=True)).to_have_count(0)
    trigger.click()
    drawer = page.get_by_role("dialog", name="Panel pemeriksaan PDPJ", exact=True)
    expect(drawer).to_contain_text("Detail PDPJ")
    drawer.get_by_role("heading", name="Detail PDPJ", exact=False).click()
    expect(drawer).to_be_visible()
    page.mouse.click(20, 200)
    expect(drawer).to_have_count(0)
    expect(trigger).to_be_focused()
    trigger.click()
    drawer.get_by_role("button", name="Tutup detail PDPJ", exact=True).click()
    expect(drawer).to_have_count(0)
