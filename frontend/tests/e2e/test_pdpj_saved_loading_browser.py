"""Reopening saved PDPJ uses cached results while explicit refresh remains fresh."""

import httpx
from playwright.sync_api import Page, expect

from test_pdpj_browser import upload_source


def test_reopening_completed_pdpj_reuses_results_and_manual_refresh_still_fetches(
    page: Page, servers: tuple[str, str]
) -> None:
    api = servers[1]
    upload_source(api, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n", "master.csv")
    batch = upload_source(api, "pdpj", "IDPEL,NAMA,LAT,LON\n001,Tersimpan,-6.2,106.8\n" * 1, "saved.csv")
    response = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": batch})
    response.raise_for_status()
    review = response.json()
    httpx.post(f"{api}/pdpj/reviews/{review['id']}/complete", json={"revision": review["revision"], "actor": "Petugas"}).raise_for_status()
    reads = []
    summary_path = f"/pdpj/reviews/{review['id']}"

    def record(request):
        path = request.url.split("?", 1)[0]
        if request.method == "GET" and (path.endswith(summary_path) or path.endswith(summary_path + "/rows")):
            reads.append(path)

    page.on("request", record)
    page.goto(f"/pdpj?batch_id={batch}&review_id={review['id']}")
    table = page.get_by_role("table")
    expect(table).to_contain_text("Tersimpan")
    expect(page.get_by_role("region", name="Ringkasan pemeriksaan PDPJ", exact=True)).to_be_visible()
    assert len(reads) == 2
    page.get_by_role("link", name="Prabayar", exact=True).click()
    expect(page.get_by_role("heading", name="Data Master Prabayar", exact=True)).to_be_visible()
    page.get_by_role("link", name="Data PDPJ", exact=True).click()
    expect(table).to_contain_text("Tersimpan")
    assert len(reads) == 2
    with page.expect_response(lambda response: response.url.split("?", 1)[0].endswith(summary_path)) as refreshed:
        page.get_by_role("button", name="Muat ulang PDPJ", exact=True).click()
    assert refreshed.value.status == 200
    expect(table).to_contain_text("Tersimpan")
    assert len(reads) > 2
