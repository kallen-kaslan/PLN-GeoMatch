"""Use PDPJ-style preview controls across all master and correction categories."""

import httpx
import pytest
from playwright.sync_api import Page, Route, expect
from test_corrections_browser import prepare, upload
from test_processing_progress_browser import captured


@pytest.mark.parametrize(
    "kind", ["prabayar", "pascabayar", "dil", "idpel_kosong", "idpel_tidak_ketemu"]
)
def test_preview_page_jump_row_counts_filters_source_changes_and_mobile(
    page: Page, servers: tuple[str, str], kind: str
) -> None:
    api = servers[1]
    master = kind in {"prabayar", "pascabayar", "dil"}
    context = "master" if master else "koreksi"
    identity = "" if kind == "idpel_kosong" else "001"
    first = upload(
        api,
        kind,
        "IDPEL,NAMA,LAT,LON\n"
        + "".join(f"{identity},Target {i:03},-6.2,106.8\n" for i in range(1, 106)),
    )
    second = upload(
        api,
        kind,
        f"IDPEL,NAMA,LAT,LON\n{identity},Kecil A,-6.2,106.8\n{identity},Kecil B,-6.2,106.8\n",
    )
    route = (
        f"/master/{kind}"
        if master
        else f"/koreksi/{kind.replace('_', '-')}?batch_id={first}"
    )
    page.goto(route)
    source = page.get_by_label(
        "Berkas sumber" if master else "Berkas koreksi", exact=True
    )
    if master:
        source.select_option(str(first))
    table = page.get_by_role("table")
    size = page.get_by_label(f"Baris per halaman {context}", exact=True)
    jump = page.get_by_label(f"Nomor halaman {context}", exact=True)
    footer = page.locator(f'footer[aria-label="Navigasi halaman {context}"]')
    expect(table.get_by_role("row")).to_have_count(26)
    expect(size).to_have_value("25")
    jump.fill("4")
    endpoint = f"/master/{kind}/records?" if master else f"/corrections/{kind}/records?"
    with page.expect_response(
        lambda response: (
            endpoint in response.url
            and "skip=75" in response.url
            and "limit=25" in response.url
        )
    ):
        jump.press("Enter")
    detail_label = "Lihat detail baris" if master else "Detail koreksi baris"
    expect(
        table.get_by_role("button", name=f"{detail_label} 77", exact=True)
    ).to_be_visible()
    expect(footer).to_contain_text("Menampilkan 76–100")
    page.get_by_role(
        "button",
        name="Halaman berikutnya" if master else "Halaman koreksi berikutnya",
        exact=True,
    ).click()
    expect(table.get_by_role("row")).to_have_count(6)
    expect(jump).to_have_value("5")
    jump.fill("6")
    footer.get_by_role("button", name="Buka halaman", exact=True).click()
    expect(footer.get_by_role("alert")).to_have_text(
        "Masukkan nomor halaman antara 1 dan 5."
    )
    jump.fill("1.5")
    footer.get_by_role("button", name="Buka halaman", exact=True).click()
    expect(footer.get_by_role("alert")).to_be_visible()
    for rows in [50, 100, 10]:
        size.select_option(str(rows))
        expect(table.get_by_role("row")).to_have_count(rows + 1)
        expect(jump).to_have_value("1")
        expect(footer.get_by_role("alert")).to_have_count(0)
    jump.fill("11")
    footer.get_by_role("button", name="Buka halaman", exact=True).click()
    expect(table.get_by_role("row")).to_have_count(6)
    page.get_by_label(
        "Cari data master" if master else "Cari data koreksi", exact=True
    ).fill("Target 105")
    expect(table.get_by_role("row")).to_have_count(2)
    expect(jump).to_have_value("1")
    status = page.get_by_label(
        "Status kelengkapan data" if master else "Filter hasil koreksi", exact=True
    )
    status.select_option("invalid" if master else "matched")
    expect(footer).to_contain_text("0 baris sesuai filter")
    expect(jump).to_be_disabled()
    expect(table.get_by_role("row")).to_have_count(2)
    page.get_by_label(
        "Cari data master" if master else "Cari data koreksi", exact=True
    ).fill("")
    status.select_option("all")
    expect(table.get_by_role("row")).to_have_count(11)
    jump.fill("11")
    footer.get_by_role("button", name="Buka halaman", exact=True).click()
    expect(jump).to_have_value("11")
    source.select_option(str(second))
    expect(table.get_by_role("row")).to_have_count(3)
    expect(jump).to_have_value("1")
    page.set_viewport_size({"width": 390, "height": 844})
    expect(jump).to_be_visible()
    expect(size).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_fast_processing_keeps_a_slow_correction_preview_request_alive(
    page: Page, servers: tuple[str, str]
) -> None:
    api = servers[1]
    review = prepare(api, candidates=2)
    batch = upload(api, "idpel_kosong", "NAMA,LAT,LON\n" + "Target,-6.2,106.8\n" * 501)
    response = httpx.post(
        f"{api}/corrections/idpel_kosong/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review,
            "radius_meters": 10,
            "actor": "Petugas",
            "request_key": "slow_source_preview",
            "incremental": True,
        },
    )
    response.raise_for_status()
    check = response.json()
    base = f"{api}/corrections/idpel_kosong/checks/{check['process_id']}"
    run = check["latest_run"]
    for _ in range(20):
        if run["processing"]["processed_rows"] >= 100:
            break
        response = httpx.post(
            base + "/advance",
            json={
                "run_id": run["id"],
                "revision": run["processing"]["revision"],
                "chunk_size": 100,
            },
        )
        response.raise_for_status()
        run = response.json()
    httpx.post(base + "/pause", json={"run_id": run["id"]}).raise_for_status()
    page.goto(
        f"/koreksi/idpel-kosong?batch_id={batch}&process_id={check['process_id']}"
    )
    table = page.get_by_role("table")
    expect(table.get_by_role("row")).to_have_count(26)
    expect(
        page.get_by_role("button", name="Lanjutkan pemeriksaan koreksi", exact=True)
    ).to_be_enabled()
    rows: list[Route] = []
    advances: list[Route] = []
    failed_rows: list[str] = []
    saved = 0

    def hold_rows(route: Route) -> None:
        if not rows:
            rows.append(route)
        else:
            route.continue_()

    def gate_advance(route: Route) -> None:
        nonlocal saved
        if saved >= 400:
            advances.append(route)
            return
        response = route.fetch()
        if response.ok:
            saved = response.json()["processing"]["processed_rows"]
        route.fulfill(response=response)

    page.route("**/corrections/idpel_kosong/records?*", hold_rows)
    page.route("**/corrections/idpel_kosong/checks/*/advance", gate_advance)
    page.on(
        "requestfailed",
        lambda request: (
            failed_rows.append(request.url) if "/records?" in request.url else None
        ),
    )
    page.get_by_label("Baris per halaman koreksi", exact=True).select_option("50")
    waiting_rows = captured(page, rows)
    page.get_by_role("button", name="Lanjutkan pemeriksaan koreksi", exact=True).click()
    waiting_advance = captured(page, advances)
    progress = page.get_by_role(
        "region", name="Progres pemeriksaan koreksi", exact=True
    )
    expect(progress).to_contain_text("400 / 501 baris")
    assert failed_rows == []
    waiting_rows.continue_()
    expect(table.get_by_role("row")).to_have_count(51)
    assert failed_rows == []
    waiting_advance.abort("failed")
