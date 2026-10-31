"""Master totals stay usable while exact detailed counts load or retry."""

import re

import pytest
from playwright.sync_api import Locator, Page, Route, expect
from test_corrections_browser import upload
from test_processing_progress_browser import captured


@pytest.mark.parametrize("kind", ["prabayar", "pascabayar", "dil"])
@pytest.mark.parametrize("fail_first", [False, True])
def test_master_totals_load_before_details_and_survive_refresh(
    page: Page, servers: tuple[str, str], kind: str, fail_first: bool
) -> None:
    upload(
        servers[1],
        kind,
        "IDPEL,NAMA,LAT,LON\n"
        "001,Lengkap,-6.2,106.8\n"
        "001,Berulang,-6.2,106.8\n"
        "002,Tanpa koordinat,,\n"
        ",Identitas kosong,-6.2,106.8\n",
    )
    held: list[Route] = []
    requests = 0
    hold = True

    def detailed_summary(route: Route) -> None:
        nonlocal requests
        requests += 1
        if hold:
            held.append(route)
        else:
            route.continue_()

    page.route(re.compile(rf"/master/{kind}/summary\?.*details=true"), detailed_summary)
    page.goto(f"/master/{kind}")
    cards = page.get_by_role("region", name="Ringkasan data master")

    def card(label: str) -> Locator:
        return (
            cards.locator("div").filter(has=page.get_by_text(label, exact=True)).first
        )

    expect(card("Total baris").locator("p").last).to_have_text("4")
    expect(card("Lolos validasi").locator("p").last).to_have_text("3")
    expect(card("Perlu perbaikan").locator("p").last).to_have_text("1")
    expect(card("Koordinat belum lengkap").locator("p").last).to_have_text("—")
    expect(page.get_by_role("table").get_by_role("row")).to_have_count(5)
    expect(page.get_by_label("Status statistik master")).to_contain_text(
        "Menghitung IDPEL unik dan kelengkapan koordinat."
    )
    pending = captured(page, held)
    if fail_first:
        pending.abort("failed")
        retry = page.get_by_role("button", name="Coba lagi statistik master")
        expect(retry).to_be_visible()
        expect(card("Total baris").locator("p").last).to_have_text("4")
        expect(page.get_by_role("table").get_by_role("row")).to_have_count(5)
        held.clear()
        retry.click()
        pending = captured(page, held)
    hold = False
    pending.continue_()
    expect(card("Koordinat belum lengkap").locator("p").last).to_have_text("1")
    expect(page.get_by_label("Status statistik master")).to_have_count(0)
    expect(page.get_by_text("2 IDPEL unik", exact=False)).to_be_visible()
    completed_requests = requests
    page.reload()
    expect(card("Total baris").locator("p").last).to_have_text("4")
    expect(card("Koordinat belum lengkap").locator("p").last).to_have_text("1")
    expect(page.get_by_text("2 IDPEL unik", exact=False)).to_be_visible()
    expect(page.get_by_label("Status statistik master")).to_have_count(0)
    assert requests == completed_requests
