"""Real stored candidates compete by distance, then download and remain editable in the map."""

from pathlib import Path

import httpx
import pytest
from openpyxl import load_workbook
from playwright.sync_api import Page, expect
from test_corrections_browser import prepare, upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_automatic_selection_preview_save_export_and_map(
    page: Page,
    servers: tuple[str, str],
    tmp_path: Path,
    kind: str,
) -> None:
    api = servers[1]
    upload(
        api,
        "dil",
        "IDPEL,NAMA,LAT,LON\n001,PDPJ,-6.3,106.8\n002,X,-6.2,106.8\n003,Y,-6.2,106.8003\n004,Z,-6.2,106.8007\n",
    )
    pdpj = upload(api, "pdpj", "IDPEL,LAT,LON\n001,-6.3,106.8\n")
    review = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": pdpj}).json()
    httpx.post(
        f"{api}/pdpj/reviews/{review['id']}/complete",
        json={"revision": review["revision"], "actor": "ignored"},
    ).raise_for_status()
    batch = upload(
        api,
        kind,
        "OBJECTID,IDPEL,NAMA,LAT,LON\n"
        + f"001,{'' if kind == 'idpel_kosong' else '777'},Target A,-6.2,106.8001\n"
        + f"002,{'' if kind == 'idpel_kosong' else '778'},Target B,-6.2,106.80002\n"
        + f"003,{'' if kind == 'idpel_kosong' else '779'},Tanpa kandidat,-6.4,106.8\n",
    )
    checked = httpx.post(
        f"{api}/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review["id"],
            "radius_meters": 250,
            "request_key": "automatic_browser_check",
            "actor": "ignored",
            "incremental": True,
        },
    )
    checked.raise_for_status()
    process = checked.json()["process_id"]
    run = checked.json()["latest_run"]
    for _ in range(12):
        if run["status"] == "completed":
            break
        response = httpx.post(
            f"{api}/corrections/{kind}/checks/{process}/advance",
            json={
                "run_id": run["id"],
                "revision": run["processing"]["revision"],
                "chunk_size": 100,
            },
        )
        response.raise_for_status()
        run = response.json()
    assert run["status"] == "completed"
    key_errors = []
    page.on(
        "console",
        lambda message: (
            key_errors.append(message.text) if "same key" in message.text else None
        ),
    )
    slug = kind.replace("_", "-")
    url = f"/koreksi/{slug}?batch_id={batch}&process_id={process}"
    if kind == "idpel_tidak_ketemu":
        page.set_viewport_size({"width": 390, "height": 844})
    page.goto(url)
    panel = page.get_by_role("region", name="Pilihan kandidat otomatis", exact=True)
    progress = page.get_by_role(
        "region", name="Progres pemeriksaan koreksi", exact=True
    )
    expect(panel).to_have_count(0)
    expect(progress).to_have_count(1)
    for _ in range(3):
        with page.expect_response(
            lambda response: (
                f"/checks/{process}?" in response.url
                and response.request.method == "GET"
            )
        ):
            page.get_by_role(
                "button", name="Muat ulang data koreksi", exact=True
            ).click()
        expect(panel).to_have_count(0)
        expect(progress).to_have_count(1)
    assert not key_errors, key_errors
    page.get_by_label("Filter radius kandidat (meter)", exact=True).fill("50")
    entry = page.get_by_role("link", name="Buka Pemilihan Otomatis", exact=True)
    expect(entry).to_have_attribute(
        "href",
        f"/koreksi/pemilihan-otomatis?category={kind}&batch_id={batch}&process_id={process}&generation=1&radius_meters=50",
    )
    entry.click()
    expect(
        page.get_by_role("heading", name="Pemilihan Otomatis", exact=True)
    ).to_be_visible()
    expect(page.get_by_label("Kategori koreksi otomatis", exact=True)).to_have_value(
        kind
    )
    expect(page.get_by_label("Berkas koreksi otomatis", exact=True)).to_have_value(
        str(batch)
    )
    expect(page.get_by_label("Pemeriksaan otomatis", exact=True)).to_have_value(
        str(process)
    )
    expect(page.get_by_label("Versi hasil otomatis", exact=True)).to_have_value("1")
    expect(panel).to_have_count(1)
    expect(progress).to_have_count(0)
    automatic_url = page.url
    radius = panel.get_by_label("Radius pilihan otomatis (meter)", exact=True)
    radius.fill("251")
    expect(
        panel.get_by_role("button", name="Pratinjau pilihan otomatis", exact=True)
    ).to_be_disabled()
    radius.fill("")
    expect(radius).to_have_value("")
    expect(
        panel.get_by_role("button", name="Pratinjau pilihan otomatis", exact=True)
    ).to_be_disabled()
    radius.fill("5")
    expect(
        panel.get_by_text("Akan dipilih otomatis", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("1")
    metrics = page.get_by_role(
        "region",
        name=f"Ringkasan {'IDPEL Kosong' if kind == 'idpel_kosong' else 'IDPEL Tidak Ketemu'}",
        exact=True,
    )
    expect(
        metrics.get_by_text("Kandidat ditemukan", exact=True)
        .locator("..")
        .get_by_text("1", exact=True)
    ).to_be_visible()
    table = page.get_by_role("table")
    expect(
        table.get_by_role("row").filter(has_text="Target A").get_by_role("cell").nth(6)
    ).to_have_text("0")
    expect(
        table.get_by_role("row").filter(has_text="Target B").get_by_role("cell").nth(6)
    ).to_have_text("1")
    page.get_by_label("Filter hasil koreksi", exact=True).select_option("matched")
    expect(table.get_by_role("row")).to_have_count(2)
    expect(table.get_by_text("Target B", exact=True)).to_be_visible()
    page.get_by_label("Filter hasil koreksi", exact=True).select_option("all")
    expect(table.get_by_role("row")).to_have_count(4)
    page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
    expect(
        detail.get_by_role("heading", name="Kandidat tersimpan (0)", exact=True)
    ).to_be_visible()
    expect(
        detail.get_by_text("Radius tersimpan 250 m (filter 5 m)", exact=False)
    ).to_be_visible()
    page.get_by_role("button", name="Tutup detail koreksi", exact=True).click()
    # A slower response for an earlier radius must not replace the latest filter.
    old_plan = httpx.post(
        f"{api}/corrections/{kind}/checks/{process}/automatic/preview",
        json={"generation": 1, "radius_meters": 10},
    ).json()
    held_requests = []

    def hold_preview(route):
        if route.request.post_data_json["radius_meters"] == 10:
            held_requests.append(route)
        else:
            route.continue_()

    preview_url = f"**/corrections/{kind}/checks/{process}/automatic/preview"
    page.route(preview_url, hold_preview)
    with page.expect_request(
        lambda request: (
            request.url.endswith("/automatic/preview")
            and request.post_data_json["radius_meters"] == 10
        )
    ):
        radius.fill("10")
    expect(radius).to_be_enabled()
    radius.fill("50")
    expect(
        panel.get_by_text("Akan dipilih otomatis", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("2")
    assert len(held_requests) == 1
    held_requests[0].fulfill(json=old_plan)
    page.unroute(preview_url, hold_preview)
    expect(radius).to_have_value("50")
    expect(
        panel.get_by_text("Akan dipilih otomatis", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("2")
    expect(
        panel.get_by_text("Memakai kandidat alternatif", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("1")
    expect(
        table.get_by_role("row").filter(has_text="Target A").get_by_role("cell").nth(6)
    ).to_have_text("2")
    expect(
        metrics.get_by_text("Kandidat ditemukan", exact=True)
        .locator("..")
        .get_by_text("2", exact=True)
    ).to_be_visible()
    page.reload()
    expect(radius).to_have_value("50")
    expect(
        panel.get_by_text("Akan dipilih otomatis", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("2")
    before = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()
    assert before["summary"]["chosen_count"] == 0

    # A download failure must keep committed choices and offer download-only retry.
    export_url = f"**/corrections/{kind}/checks/{process}/results/export?*"
    page.route(
        export_url,
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"Unduhan sementara gagal"}',
        ),
    )
    panel.get_by_role("button", name="Simpan & ekspor XLSX", exact=True).click()
    expect(
        panel.get_by_role("status").filter(
            has_text="2 pilihan otomatis sudah tersimpan"
        )
    ).to_be_visible()
    expect(
        panel.get_by_role("alert").filter(has_text="Pilihan sudah tersimpan")
    ).to_be_visible()
    page.unroute(export_url)
    with page.expect_download() as downloaded:
        panel.get_by_role("button", name="Unduh ulang XLSX", exact=True).click()
    path = tmp_path / "automatic.xlsx"
    downloaded.value.save_as(path)
    book = load_workbook(path)
    assert book.sheetnames == ["Hasil Koreksi"]
    values = list(book.active.values)
    assert [row[0] for row in values[1:]] == ["001", "002"]
    assert [row[2] for row in values[1:]] == ["003", "002"]
    assert all(row[-2] == 50 and 0 < row[-1] <= 50 for row in values[1:])
    book.close()
    results = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()
    assert (
        results["summary"]["chosen_count"] == results["summary"]["decision_events"] == 2
    )
    assert all(item["choice"]["actor"] == "test-admin" for item in results["items"])
    panel.get_by_role("link", name="Buka Peta Koreksi", exact=True).click()
    expect(page.get_by_role("heading", name="Peta Koreksi", exact=True)).to_be_visible()
    page.goto(automatic_url)
    panel = page.get_by_role("region", name="Pilihan kandidat otomatis", exact=True)
    panel.get_by_label("Radius pilihan otomatis (meter)", exact=True).fill("50")
    expect(
        panel.get_by_text("Keputusan tersimpan dipertahankan", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("2")
    expect(
        panel.get_by_text("Akan dipilih otomatis", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("0")
    expect(progress).to_have_count(0)
    page.get_by_role("link", name="Kembali ke pemeriksaan asal", exact=True).click()
    expect(
        page.get_by_label("Filter radius kandidat (meter)", exact=True)
    ).to_have_value("50")
    expect(panel).to_have_count(0)
    expect(progress).to_have_count(1)
    if kind == "idpel_tidak_ketemu":
        page.get_by_role("button", name="Buka menu navigasi", exact=True).click()
    page.get_by_role("navigation", name="Menu utama", exact=True).get_by_role(
        "link", name="Pemilihan Otomatis", exact=True
    ).click()
    expect(
        page.get_by_role("heading", name="Pemilihan Otomatis", exact=True)
    ).to_be_visible()
    page.get_by_label("Kategori koreksi otomatis", exact=True).select_option(kind)
    expect(page.get_by_label("Pemeriksaan otomatis", exact=True)).to_have_value(
        str(process)
    )
    expect(
        panel.get_by_text("Keputusan tersimpan dipertahankan", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("2")
    assert not key_errors, key_errors


def test_automatic_page_handles_empty_unfinished_and_mismatched_sources(page, servers):
    api = servers[1]
    page.goto("/koreksi/pemilihan-otomatis")
    expect(
        page.get_by_role("heading", name="Pemilihan Otomatis", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("status").filter(
            has_text="Belum ada pemeriksaan untuk pemilihan otomatis"
        )
    ).to_be_visible()
    assert (
        page.get_by_role("region", name="Pilihan kandidat otomatis", exact=True).count()
        == 0
    )
    review = prepare(api, candidates=2)
    batch = upload(api, "idpel_kosong", "NAMA,LAT,LON\nTarget,-6.2,106.8\n")
    checked = httpx.post(
        f"{api}/corrections/idpel_kosong/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review,
            "radius_meters": 100,
            "actor": "ignored",
            "request_key": "automatic_unfinished_01",
            "incremental": True,
        },
    )
    checked.raise_for_status()
    process = checked.json()["process_id"]
    automated_requests = []
    page.on(
        "request",
        lambda request: (
            automated_requests.append(request.url)
            if "/automatic/" in request.url
            else None
        ),
    )
    page.goto(
        f"/koreksi/pemilihan-otomatis?category=idpel_kosong&batch_id={batch}&process_id={process}"
    )
    expect(
        page.get_by_role("status").filter(
            has_text="Pemilihan otomatis hanya tersedia pada hasil terbaru yang sudah selesai"
        )
    ).to_be_visible()
    expect(
        page.get_by_role("region", name="Pilihan kandidat otomatis", exact=True)
    ).to_have_count(0)
    other = upload(api, "idpel_kosong", "NAMA,LAT,LON\nOther,-6.2,106.8\n")
    page.goto(
        f"/koreksi/pemilihan-otomatis?category=idpel_kosong&batch_id={other}&process_id={process}"
    )
    expect(
        page.get_by_role("alert").filter(
            has_text="Berkas, pemeriksaan, atau versi tidak sesuai"
        )
    ).to_be_visible()
    expect(
        page.get_by_role("region", name="Pilihan kandidat otomatis", exact=True)
    ).to_have_count(0)
    assert not automated_requests
