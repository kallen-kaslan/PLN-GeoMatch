"""Complete selection saves ties and expanded pairs, then exports all active results."""

import httpx
import pytest
from openpyxl import load_workbook
from playwright.sync_api import expect
from test_corrections_browser import upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_complete_save_export_result_and_inherited_map_candidates(
    page, servers, tmp_path, kind
):
    api = servers[1]
    upload(
        api,
        "dil",
        "IDPEL,NAMA,LAT,LON\n001,PDPJ,-6.3,106.8\n002,A,-6.2,106.8\n003,B,-6.2,106.8\n020,C,-6.2005,106.8\n021,D,-6.201,106.8\n030,E,-6.203,106.8\n",
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
        + "".join(
            f"00{i},{'' if kind == 'idpel_kosong' else str(770 + i)},Target {i},-6.2,106.8\n"
            for i in range(1, 6)
        ),
    )
    checked = httpx.post(
        f"{api}/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review["id"],
            "radius_meters": 10,
            "actor": "ignored",
            "incremental": True,
            "request_key": "complete_browser_check",
        },
    )
    checked.raise_for_status()
    process = checked.json()["process_id"]
    base = f"{api}/corrections/{kind}/checks/{process}"
    run = checked.json()["latest_run"]
    for _ in range(30):
        if run["status"] == "completed":
            break
        advanced = httpx.post(
            base + "/advance",
            json={
                "run_id": run["id"],
                "revision": run["processing"]["revision"],
                "chunk_size": 100,
            },
        )
        advanced.raise_for_status()
        run = advanced.json()
    assert run["status"] == "completed"
    first = httpx.get(base + "/results", params={"status": "all"}).json()["items"][0]
    details = httpx.get(
        f"{api}/corrections/{kind}/records/{first['record_id']}",
        params={"process_id": process, "generation": 1},
    ).json()
    candidate = next(
        item for item in details["candidates"] if item["fields"]["idpel"] == "002"
    )
    chosen = httpx.post(
        base + f"/records/{first['record_id']}/choice",
        json={
            "generation": 1,
            "expected_revision": 0,
            "candidate_id": candidate["id"],
            "reason": "Pilihan awal terverifikasi",
            "actor": "ignored",
            "request_key": "complete_browser_protected",
        },
    )
    chosen.raise_for_status()
    protected = chosen.json()["current"]["id"]
    if kind == "idpel_tidak_ketemu":
        page.set_viewport_size({"width": 390, "height": 844})
    page.goto(
        f"/koreksi/pemilihan-otomatis?category={kind}&batch_id={batch}&process_id={process}"
    )
    page.get_by_label("Penanganan jarak sama", exact=True).select_option("complete")
    panel = page.get_by_role("region", name="Pemilihan otomatis lengkap", exact=True)
    expect(
        panel.get_by_label("Batas radius otomatis (meter)", exact=True)
    ).to_have_value("500")
    panel.get_by_role("button", name="Pratinjau lengkap", exact=True).click()
    expect(
        panel.get_by_text("Pilihan baru yang akan disimpan", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("4")
    expect(
        panel.get_by_text("Keputusan tersimpan dipertahankan", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("1")
    expect(
        panel.get_by_text("Belum mendapat pasangan", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("0")
    assert httpx.get(base + "/results").json()["summary"]["chosen_count"] == 1
    with page.expect_download() as download:
        panel.get_by_role(
            "button", name="Simpan seluruh pasangan otomatis & ekspor", exact=True
        ).click()
    path = tmp_path / download.value.suggested_filename
    download.value.save_as(path)
    book = load_workbook(path)
    assert book.sheetnames == ["Hasil Koreksi"]
    values = list(book.active.values)
    assert len(values) == 6 and len(values[0]) == 12
    assert {row[0] for row in values[1:]} == {"001", "002", "003", "004", "005"}
    assert {row[2] for row in values[1:]} == {"002", "003", "020", "021", "030"}
    assert all(row[10] == 500 for row in values[1:])
    expect(
        panel.get_by_role("status").filter(
            has_text="4 pilihan otomatis lengkap tersimpan pada versi 2, radius 500 m"
        )
    ).to_be_visible()
    after = httpx.get(base + "/results").json()
    assert after["summary"]["chosen_count"] == after["summary"]["total_targets"] == 5
    assert after["summary"]["not_selected"] == 0
    assert after["items"][0]["choice"]["id"] == protected
    panel.get_by_role("link", name="Lihat hasil tersimpan", exact=True).click()
    expect(
        page.get_by_label("Filter radius hasil ekspor (meter)", exact=True)
    ).to_have_value("500")
    expect(
        page.get_by_role("heading", name="Hasil Koreksi", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_text("Otomatis · Identitas belum diverifikasi", exact=True)
    ).to_have_count(4)
    assert (
        httpx.get(base + "/results", params={"generation": 1}).json()["summary"][
            "chosen_count"
        ]
        == 1
    )
    last = after["items"][-1]
    page.goto(
        f"/peta-koreksi?category={kind}&batch_id={batch}&process_id={process}&generation=2&radius_meters=500&record_id={last['record_id']}&map_view=detail"
    )
    expect(
        page.get_by_role("article", name="Kandidat peta 1", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("article", name="Kandidat peta 3", exact=True)
    ).to_be_visible()
    assert httpx.get(base + "/results").json()["summary"]["chosen_count"] == 5
