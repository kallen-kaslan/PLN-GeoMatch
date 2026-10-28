"""Jump to PDPJ pages and change the number of preview rows through the real API."""

import httpx
from playwright.sync_api import Page, Route, expect

from test_pdpj_browser import upload_source
from test_processing_progress_browser import captured


def test_jump_page_preview_size_filters_and_mobile_layout(page: Page, servers: tuple[str, str]) -> None:
    api = servers[1]
    upload_source(api, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n", "master.csv")
    batch = upload_source(api, "pdpj", "IDPEL,NAMA,LAT,LON\n" + "".join(f"001,Target {i:03},-6.2,106.8\n" for i in range(1, 106)), "preview.csv")
    response = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": batch}, timeout=30)
    response.raise_for_status()
    review = response.json()["id"]
    page.goto(f"/pdpj?batch_id={batch}&review_id={review}")
    table = page.get_by_role("table")
    size = page.get_by_label("Baris per halaman PDPJ", exact=True)
    jump = page.get_by_label("Nomor halaman PDPJ", exact=True)
    submit = page.get_by_role("button", name="Buka halaman", exact=True)
    expect(table.get_by_role("row")).to_have_count(26)
    expect(size).to_have_value("25")
    jump.fill("4")
    with page.expect_response(lambda response: f"/pdpj/reviews/{review}/rows?" in response.url and "skip=75" in response.url and "limit=25" in response.url) as jumped:
        jump.press("Enter")
    assert jumped.value.status == 200
    expect(table.get_by_role("button", name="Detail PDPJ baris 77", exact=True)).to_be_visible()
    expect(jump).to_have_value("4")
    page.get_by_role("button", name="Halaman PDPJ berikutnya", exact=True).click()
    expect(table.get_by_role("row")).to_have_count(6)
    expect(table.get_by_role("button", name="Detail PDPJ baris 106", exact=True)).to_be_visible()
    expect(jump).to_have_value("5")
    expect(page.get_by_role("button", name="Halaman PDPJ berikutnya", exact=True)).to_be_disabled()
    jump.fill("6")
    submit.click()
    expect(page.get_by_role("alert")).to_have_text("Masukkan nomor halaman antara 1 dan 5.")
    expect(table.get_by_role("row")).to_have_count(6)
    jump.fill("1.5")
    submit.click()
    expect(page.get_by_role("alert")).to_have_text("Masukkan nomor halaman antara 1 dan 5.")
    size.select_option("50")
    expect(table.get_by_role("row")).to_have_count(51)
    expect(jump).to_have_value("1")
    expect(page.get_by_role("alert")).to_have_count(0)
    jump.fill("3")
    submit.click()
    expect(table.get_by_role("row")).to_have_count(6)
    expect(table.get_by_role("button", name="Detail PDPJ baris 102", exact=True)).to_be_visible()
    size.select_option("100")
    expect(table.get_by_role("row")).to_have_count(101)
    expect(jump).to_have_value("1")
    size.select_option("10")
    expect(table.get_by_role("row")).to_have_count(11)
    jump.fill("11")
    submit.click()
    expect(table.get_by_role("row")).to_have_count(6)
    page.get_by_label("Cari data PDPJ", exact=True).fill("Target 105")
    expect(table.get_by_role("row")).to_have_count(2)
    expect(jump).to_have_value("1")
    expect(table.get_by_role("button", name="Detail PDPJ baris 106", exact=True)).to_be_visible()
    page.get_by_label("Filter pemeriksaan PDPJ", exact=True).select_option("not_found")
    expect(table.get_by_text("Tidak ada baris sesuai filter.", exact=True)).to_be_visible()
    expect(jump).to_be_disabled()
    expect(submit).to_be_disabled()
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_label("Cari data PDPJ", exact=True).fill("")
    page.get_by_label("Filter pemeriksaan PDPJ", exact=True).select_option("all")
    expect(table.get_by_role("row")).to_have_count(11)
    expect(jump).to_be_enabled()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_fast_progress_does_not_cancel_a_slow_table_request(page: Page, servers: tuple[str, str]) -> None:
    api = servers[1]
    upload_source(api, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n", "master.csv")
    batch = upload_source(api, "pdpj", "IDPEL,NAMA,LAT,LON\n" + "001,Target,-6.2,106.8\n" * 501, "live-preview.csv")
    response = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": batch, "incremental": True})
    response.raise_for_status()
    review = response.json()["id"]
    delayed_rows: list[Route] = []
    delayed_advance: list[Route] = []
    failed_rows: list[str] = []
    saved_parts = 0

    def hold_first_rows(route: Route) -> None:
        if not delayed_rows:
            delayed_rows.append(route)
        else:
            route.continue_()

    def hold_after_three_parts(route: Route) -> None:
        nonlocal saved_parts
        if saved_parts == 3:
            delayed_advance.append(route)
            return
        result = route.fetch()
        if result.ok and result.json()["processing"]["processed_rows"] > 0:
            saved_parts += 1
        route.fulfill(response=result)

    page.route(f"**/pdpj/reviews/{review}/rows?**", hold_first_rows)
    page.route(f"**/pdpj/reviews/{review}/advance", hold_after_three_parts)
    page.on("requestfailed", lambda request: failed_rows.append(request.url) if f"/pdpj/reviews/{review}/rows?" in request.url else None)
    page.goto(f"/pdpj?batch_id={batch}&review_id={review}")
    progress = page.get_by_role("region", name="Progres pemeriksaan PDPJ", exact=True)
    progress.get_by_role("button", name="Lanjutkan pemeriksaan", exact=True).click()
    active = captured(page, delayed_advance)
    assert failed_rows == []
    captured(page, delayed_rows).continue_()
    expect(page.get_by_role("table").get_by_role("row")).to_have_count(26)
    expect(page.get_by_role("button", name="Detail PDPJ baris 2", exact=True)).to_be_visible()
    expect(progress).to_have_attribute("aria-busy", "true")
    assert failed_rows == []
    progress.get_by_role("button", name="Hentikan sementara", exact=True).click()
    active.abort("failed")
    expect(progress.get_by_role("status")).to_have_text("Proses dijeda · siap dilanjutkan")
