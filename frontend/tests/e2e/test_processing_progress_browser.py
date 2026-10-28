"""Observe progress before completion, including saving animations and recovery."""

import httpx
import time
from playwright.sync_api import Page, Route, expect

from test_corrections_browser import prepare, upload
from test_pdpj_progress_browser import sources


def captured(page: Page, routes: list[Route]) -> Route:
    deadline = time.monotonic() + 5
    while not routes and time.monotonic() < deadline:
        page.wait_for_timeout(20)
    assert routes, "The active save request was not received"
    return routes[0]


def test_small_pdpj_progress_is_visible_for_a_large_file(page: Page, servers: tuple[str, str]) -> None:
    batch = sources(servers[1], 20001)
    requests: list[Route] = []
    calls = 0

    def hold(route: Route) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            requests.append(route)
        else:
            route.abort("failed")

    page.route("**/pdpj/reviews/*/advance", hold)
    page.goto(f"/pdpj?batch_id={batch}")
    page.get_by_role("button", name="Periksa IDPEL ke master", exact=True).click()
    progress = page.get_by_role("region", name="Progres pemeriksaan PDPJ")
    expect(progress).to_have_attribute("aria-busy", "true")
    expect(progress.get_by_text("Memproses dan menyimpan bagian aktif…", exact=False)).to_be_visible()
    captured(page, requests).continue_()
    expect(progress.get_by_role("alert")).to_be_visible()
    assert 0 < float(progress.get_by_role("progressbar").get_attribute("value")) < 1
    expect(progress.get_by_text("0,25%", exact=True)).to_be_visible()
    expect(progress.get_by_text("100 / 20.001 baris", exact=True)).to_be_visible()


def test_final_validation_and_approval_saving_are_visible(page: Page, servers: tuple[str, str]) -> None:
    batch = sources(servers[1], 305)
    held: list[Route] = []
    hold_next = False
    held_once = False

    def observe(route: Route) -> None:
        nonlocal hold_next, held_once
        if hold_next and not held_once:
            held_once = True
            held.append(route)
            return
        response = route.fetch()
        if response.ok and response.json()["processing"]["validated_rows"] == 100:
            hold_next = True
        route.fulfill(response=response)

    page.route("**/pdpj/reviews/*/advance", observe)
    page.goto(f"/pdpj?batch_id={batch}")
    page.get_by_role("button", name="Periksa IDPEL ke master", exact=True).click()
    progress = page.get_by_role("region", name="Progres pemeriksaan PDPJ")
    expect(progress.get_by_role("heading", name="Memvalidasi dan menyimpan hasil akhir", exact=True)).to_be_visible(timeout=20000)
    expect(progress.get_by_text("100 / 305 baris", exact=True)).to_be_visible(timeout=20000)
    expect(progress).to_have_attribute("aria-busy", "true")
    assert 50 < float(progress.get_by_role("progressbar").get_attribute("value")) < 100
    expect(progress.get_by_text("Memeriksa dan menyimpan validasi akhir bagian aktif…", exact=False)).to_be_visible()
    captured(page, held).continue_()
    expect(progress.get_by_role("progressbar")).to_have_attribute("value", "100", timeout=20000)
    expect(progress.get_by_text("305 / 305 baris", exact=True)).to_have_count(2)
    approval: list[Route] = []
    page.route("**/pdpj/reviews/*/complete", lambda route: approval.append(route))
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Progres")
    page.get_by_role("button", name="Selesaikan validasi PDPJ", exact=True).click()
    expect(progress.get_by_role("heading", name="Menyimpan hasil validasi yang disetujui", exact=True)).to_be_visible()
    expect(progress).to_have_attribute("aria-busy", "true")
    captured(page, approval).continue_()
    expect(page.get_by_role("dialog", name="PDPJ selesai divalidasi", exact=True)).to_be_visible()


def test_correction_progress_saves_pauses_and_resumes_after_reload(page: Page, servers: tuple[str, str]) -> None:
    api = servers[1]
    prepare(api, candidates=2)
    batch = upload(api, "idpel_kosong", "NAMA,LAT,LON\n" + "Target,-6.2,106.8\n" * 1001)
    page.goto(f"/koreksi/idpel-kosong?batch_id={batch}")
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Progres")
    page.get_by_label("Radius pemeriksaan (meter)", exact=True).fill("10")
    with page.expect_response(lambda response: response.url.endswith("/advance") and response.status == 200 and response.json()["processing"]["processed_rows"] >= 100):
        page.get_by_role("button", name="Jalankan pemeriksaan", exact=True).click()
    progress = page.get_by_role("region", name="Progres pemeriksaan koreksi")
    page.get_by_role("button", name="Hentikan sementara koreksi", exact=True).click()
    expect(progress.get_by_role("status")).to_have_text("Proses dijeda · siap dilanjutkan")
    assert 0 < float(progress.get_by_role("progressbar").get_attribute("value")) < 100
    process = int(page.url.split("process_id=")[1])
    path = f"{api}/corrections/idpel_kosong/checks/{process}"
    stored = httpx.get(path).json()["latest_run"]
    assert 100 <= stored["processing"]["processed_rows"] < 1001
    assert stored["processing"]["state"] == "paused"
    first_row = page.get_by_role("row").filter(has=page.get_by_role("button", name="Detail koreksi baris 2", exact=True))
    expect(first_row.get_by_text("Kandidat ditemukan", exact=True)).to_be_visible()
    summary = page.get_by_role("region", name="Ringkasan IDPEL Kosong", exact=True)
    expect(summary.get_by_text("Belum diperiksa", exact=True).locator("..").get_by_text(str(1001 - stored["processing"]["processed_rows"]), exact=True)).to_be_visible()
    page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
    expect(detail.get_by_role("heading", name="Kandidat tersimpan (2)", exact=True)).to_be_visible()
    page.reload()
    expect(progress.get_by_role("button", name="Lanjutkan pemeriksaan koreksi", exact=True)).to_be_visible()
    expect(first_row.get_by_text("Kandidat ditemukan", exact=True)).to_be_visible()
    assert httpx.get(path).json()["latest_run"]["processing"] == stored["processing"]
    page.get_by_role("button", name="Lanjutkan pemeriksaan koreksi", exact=True).click()
    expect(progress.get_by_role("progressbar")).to_have_attribute("value", "100", timeout=30000)
    completed = httpx.get(path).json()
    assert completed["latest_run"]["id"] == stored["id"]
    assert completed["latest_run"]["processing"]["validated_rows"] == 1001
    assert completed["current_generation"] == 1


def test_committed_correction_rows_refresh_while_next_chunk_is_running(page: Page, servers: tuple[str, str]) -> None:
    api = servers[1]
    prepare(api, candidates=2)
    batch = upload(api, "idpel_kosong", "NAMA,LAT,LON\n" + "Target,-6.2,106.8\n" * 201)
    held: list[Route] = []
    saved = False

    def hold_after_saved(route: Route) -> None:
        nonlocal saved
        if saved:
            held.append(route)
            return
        response = route.fetch()
        if response.ok and response.json()["processing"]["processed_rows"] == 100:
            saved = True
        route.fulfill(response=response)

    page.route("**/corrections/idpel_kosong/checks/*/advance", hold_after_saved)
    page.goto(f"/koreksi/idpel-kosong?batch_id={batch}")
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Progres")
    page.get_by_label("Radius pemeriksaan (meter)", exact=True).fill("10")
    page.get_by_role("button", name="Jalankan pemeriksaan", exact=True).click()
    active = captured(page, held)
    first_row = page.get_by_role("row").filter(has=page.get_by_role("button", name="Detail koreksi baris 2", exact=True))
    expect(first_row.get_by_text("Kandidat ditemukan", exact=True)).to_be_visible()
    expect(page.get_by_text("Menampilkan hasil sementara versi 1 yang sudah tersimpan.", exact=False)).to_be_visible()
    page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
    expect(detail.get_by_role("heading", name="Kandidat tersimpan (2)", exact=True)).to_be_visible()
    page.get_by_role("button", name="Tutup detail koreksi", exact=True).click()
    page.get_by_label("Filter hasil koreksi", exact=True).select_option("not_checked")
    page.get_by_role("button", name="Detail koreksi baris 102", exact=True).click()
    expect(detail.get_by_role("heading", name="Kandidat tersimpan (0)", exact=True)).to_be_visible()
    active.continue_()
    expect(detail.get_by_role("heading", name="Kandidat tersimpan (2)", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Detail koreksi baris 202", exact=True)).to_be_visible()
    assert len(held) == 2
    held[-1].abort("failed")
