"""Exercise real saved checkpoints through stop, reload, and connection recovery."""

import httpx
from playwright.sync_api import Page, Route, expect

from test_pdpj_browser import upload_source


def sources(api: str, total: int) -> int:
    upload_source(api, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n", "master-progress.csv")
    return upload_source(api, "pdpj", "IDPEL,LAT,LON\n" + "001,-6.2,106.8\n" * total, "pdpj-progress.csv")


def test_stop_reload_and_resume_from_saved_rows(page: Page, servers: tuple[str, str]) -> None:
    api = servers[1]
    batch = sources(api, 2401)
    page.goto(f"/pdpj?batch_id={batch}")
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Progres")
    with page.expect_response(lambda response: response.url.endswith("/advance") and response.status == 200):
        page.get_by_role("button", name="Periksa IDPEL ke master", exact=True).click()
    page.get_by_role("button", name="Hentikan sementara", exact=True).click()
    progress = page.get_by_role("region", name="Progres pemeriksaan PDPJ")
    expect(progress.get_by_role("status")).to_have_text("Proses dijeda · siap dilanjutkan")
    review_id = int(page.url.split("review_id=")[1])
    path = f"{api}/pdpj/reviews/{review_id}"
    saved = httpx.get(path).json()
    assert 400 <= saved["processing"]["processed_rows"] < 2401
    assert saved["processing"]["state"] == "paused"
    original = httpx.get(path + "/rows").json()["items"][0]
    page.reload()
    expect(progress.get_by_role("button", name="Lanjutkan pemeriksaan", exact=True)).to_be_visible()
    assert httpx.get(path).json()["processing"] == saved["processing"]
    expect(page.get_by_role("button", name="Selesaikan validasi PDPJ", exact=True)).to_be_disabled()
    page.get_by_role("button", name="Lanjutkan pemeriksaan", exact=True).click()
    expect(progress.get_by_role("progressbar")).to_have_attribute("value", "100", timeout=30000)
    expect(progress.get_by_role("status")).to_have_text("Menunggu tinjauan petugas")
    finished = httpx.get(path).json()
    assert finished["processing"]["processed_rows"] == finished["processing"]["validated_rows"] == 2401
    assert finished["summary"]["found"] == finished["summary"]["total_rows"] == 2401
    assert httpx.get(path + "/rows").json()["items"][0]["id"] == original["id"]


def test_connection_loss_keeps_checkpoint_and_reload_can_continue(page: Page, servers: tuple[str, str]) -> None:
    api = servers[1]
    batch = sources(api, 805)
    calls = 0

    def interrupt(route: Route) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            # The save succeeds, but the browser never receives its response.
            # Resume must trust the database cursor, not its last local count.
            response = route.fetch()
            assert response.status == 200
            route.abort("failed")
        else:
            route.continue_()

    page.route("**/pdpj/reviews/*/advance", interrupt)
    page.goto(f"/pdpj?batch_id={batch}")
    page.get_by_role("button", name="Periksa IDPEL ke master", exact=True).click()
    progress = page.get_by_role("region", name="Progres pemeriksaan PDPJ")
    expect(progress.get_by_role("alert")).to_be_visible()
    review_id = int(page.url.split("review_id=")[1])
    path = f"{api}/pdpj/reviews/{review_id}"
    assert httpx.get(path).json()["processing"]["processed_rows"] == 800
    page.unroute("**/pdpj/reviews/*/advance", interrupt)
    page.reload()
    page.get_by_role("button", name="Lanjutkan pemeriksaan", exact=True).click()
    expect(progress.get_by_role("progressbar")).to_have_attribute("value", "100", timeout=30000)
    assert httpx.get(path).json()["summary"]["found"] == 805
