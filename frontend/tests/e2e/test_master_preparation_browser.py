"""See master preparation progress, pause it, resume it, and reuse the ready snapshot."""

import httpx
from playwright.sync_api import Page, Route, expect

from test_corrections_browser import upload
from test_processing_progress_browser import captured


def test_master_progress_is_saved_and_ready_snapshot_can_be_reused(page: Page, servers: tuple[str, str]) -> None:
    api = servers[1]
    upload(api, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n")
    upload(api, "dil", "IDPEL,LAT,LON\n" + "".join(f"{101 + i % 50:03},-7.0,107.0\n" for i in range(5001)))
    pdpj = upload(api, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    review = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": pdpj}).json()
    response = httpx.post(f"{api}/pdpj/reviews/{review['id']}/complete", json={"revision": review["revision"], "actor": "Petugas"})
    response.raise_for_status()
    target = upload(api, "idpel_kosong", "NAMA,LAT,LON\nTarget,-6.2,106.8\n")
    held: list[Route] = []
    calls = 0

    def hold_second(route: Route) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            held.append(route)
        else:
            route.continue_()

    page.route("**/corrections/idpel_kosong/checks/*/advance", hold_second)
    page.goto(f"/koreksi/idpel-kosong?batch_id={target}")
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Persiapan")
    page.get_by_label("Radius pemeriksaan (meter)", exact=True).fill("10")
    page.get_by_role("button", name="Jalankan pemeriksaan", exact=True).click()
    progress = page.get_by_role("region", name="Progres pemeriksaan koreksi")
    preparation = progress.get_by_label("Progres persiapan master", exact=True)
    expect(preparation.get_by_text("2.000 / 5.003 baris", exact=True)).to_be_visible(timeout=20000)
    assert 0 < float(progress.get_by_role("progressbar").get_attribute("value")) < 100
    expect(progress.get_by_text("Baris koreksi tersimpan", exact=True).locator("..").get_by_text("0 / 1 baris", exact=True)).to_be_visible()
    expect(progress.get_by_text("Validasi akhir tersimpan", exact=True).locator("..").get_by_text("0 / 1 baris", exact=True)).to_be_visible()
    page.get_by_role("button", name="Hentikan sementara koreksi", exact=True).click()
    captured(page, held).abort("failed")
    expect(progress.get_by_role("status")).to_have_text("Proses dijeda · siap dilanjutkan")
    process_id = int(page.url.split("process_id=")[1])
    path = f"{api}/corrections/idpel_kosong/checks/{process_id}"
    before = httpx.get(path).json()["latest_run"]["processing"]["preparation"]
    assert before["source_rows"] == 2000
    page.unroute("**/corrections/idpel_kosong/checks/*/advance", hold_second)
    page.reload()
    expect(preparation.get_by_text("2.000 / 5.003 baris", exact=True)).to_be_visible()
    page.get_by_role("button", name="Lanjutkan pemeriksaan koreksi", exact=True).click()
    expect(page.get_by_role("dialog", name="Pemeriksaan koreksi selesai", exact=True)).to_be_visible(timeout=30000)
    ready = httpx.get(path).json()
    assert ready["latest_run"]["processing"]["preparation"]["source_rows"] == 5003
    assert ready["latest_run"]["processing"]["preparation"]["cached_rows"] == 5003
    page.get_by_role("button", name="Lihat hasil pemeriksaan", exact=True).click()
    expect(preparation.get_by_text("5.003 / 5.003 baris", exact=True)).to_be_visible()
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Persiapan")
    page.get_by_role("button", name="Pemeriksaan baru", exact=True).click()
    expect(page.get_by_role("dialog", name="Pemeriksaan koreksi selesai", exact=True)).to_be_visible(timeout=20000)
    page.get_by_role("button", name="Lihat hasil pemeriksaan", exact=True).click()
    expect(page.get_by_text("Snapshot master yang sesuai digunakan kembali", exact=True)).to_be_visible()
    later_process = int(page.url.split("process_id=")[1])
    reused = httpx.get(f"{api}/corrections/idpel_kosong/checks/{later_process}").json()
    assert reused["master_snapshot_id"] == ready["master_snapshot_id"]
    assert reused["latest_run"]["processing"]["preparation"]["reused"] is True
