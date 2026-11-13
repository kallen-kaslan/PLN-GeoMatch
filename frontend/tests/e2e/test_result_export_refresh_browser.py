"""Background result polling must not disable or flash the export action."""

import re

import httpx
import pytest
from openpyxl import load_workbook
from playwright.sync_api import expect
from test_corrections_browser import prepare, upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_export_stays_available_during_background_refresh_and_uses_current_radius(
    page, servers, tmp_path, kind
):
    api = servers[1]
    review = prepare(api, candidates=2)
    batch = upload(
        api,
        kind,
        "IDPEL,NAMA,LAT,LON\n"
        + (
            ",Target,-6.2,106.8\n"
            if kind == "idpel_kosong"
            else "999,Target,-6.2,106.8\n"
        ),
    )
    checked = httpx.post(
        f"{api}/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review,
            "radius_meters": 10,
            "actor": "ignored",
            "request_key": "export_refresh_check",
        },
        timeout=30,
    )
    checked.raise_for_status()
    process = checked.json()["process_id"]
    base = f"{api}/corrections/{kind}/checks/{process}"
    record = httpx.get(
        f"{api}/corrections/{kind}/records", params={"process_id": process}
    ).json()["items"][0]
    detail = httpx.get(
        f"{api}/corrections/{kind}/records/{record['id']}",
        params={"process_id": process},
    ).json()
    chosen = httpx.post(
        base + f"/records/{record['id']}/choice",
        json={
            "generation": 1,
            "expected_revision": 0,
            "candidate_id": detail["candidates"][0]["id"],
            "actor": "ignored",
            "reason": "Bukti sesuai",
            "request_key": "export_refresh_choice",
        },
    )
    chosen.raise_for_status()
    page.goto(
        f"/result?category={kind}&process_id={process}&generation=1&radius_meters=5"
    )
    export = page.get_by_role("button", name="Ekspor hasil XLSX", exact=True)
    expect(export).to_be_enabled()
    pattern = re.compile(rf"/corrections/{kind}/checks/{process}/results\?")
    held = []
    page.route(pattern, lambda route: held.append(route))
    try:
        with page.expect_request(pattern, timeout=15000):
            pass  # Wait for the real five-second polling cycle.
        reload = page.get_by_role("button", name="Muat ulang hasil", exact=True)
        expect(reload).to_be_enabled()
        expect(reload).to_have_attribute("aria-busy", "false")
        expect(export).to_be_enabled()
        expect(export).to_have_text("Ekspor hasil XLSX")
        with page.expect_download() as download:
            export.click()
        path = tmp_path / download.value.suggested_filename
        download.value.save_as(path)
        book = load_workbook(path)
        values = list(book["Hasil Koreksi"].values)
        assert len(values) == 2 and values[1][2] == "002"
        assert values[1][10] == 5
        book.close()
        reload.click()
        expect(reload).to_be_disabled()
        expect(reload).to_have_attribute("aria-busy", "true")
        expect(reload).to_have_text("Memuat ulang...")
        expect(export).to_be_enabled()
        assert (
            len(held) == 1
        )  # Manual refresh joins the existing poll instead of restarting it.
    finally:
        for route in held:
            route.continue_()
        page.unroute(pattern)
    expect(export).to_be_enabled()
    expect(reload).to_be_enabled()
    expect(reload).to_have_attribute("aria-busy", "false")
    expect(reload).to_have_text("Muat ulang hasil")
    page.get_by_label("Filter radius hasil ekspor (meter)", exact=True).fill("0")
    expect(export).to_be_disabled()
    expect(reload).to_be_disabled()
