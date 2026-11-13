"""History deletion works with saved correction choices and active-work errors."""

import httpx
import pytest
from playwright.sync_api import Page, expect
from test_corrections_browser import prepare, upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_delete_one_then_all_saved_correction_history(
    page: Page, servers: tuple[str, str], kind: str,
) -> None:
    api = servers[1]
    review = prepare(api, candidates=2)
    identity = "" if kind == "idpel_kosong" else "999"
    batch = upload(api, kind, f"IDPEL,LAT,LON\n{identity},-6.2,106.8\n")
    processes = []
    for number in (1, 2):
        response = httpx.post(f"{api}/corrections/{kind}/checks", json={
            "batch_id": batch, "pdpj_review_id": review, "radius_meters": 10,
            "actor": "Uji Hapus", "request_key": f"browser_delete_{number}",
        }, timeout=30)
        response.raise_for_status()
        process = response.json()["process_id"]
        record = httpx.get(f"{api}/corrections/{kind}/records", params={"process_id": process}).json()["items"][0]
        detail = httpx.get(f"{api}/corrections/{kind}/records/{record['id']}", params={"process_id": process}).json()
        response = httpx.post(f"{api}/corrections/{kind}/checks/{process}/records/{record['id']}/choice", json={
            "generation": 1, "expected_revision": 0, "candidate_id": detail["candidates"][0]["id"],
            "actor": "Uji Hapus", "request_key": f"browser_delete_choice_{number}",
        })
        response.raise_for_status()
        processes.append(process)
    page.goto("/history")
    table = page.get_by_role("table")
    selected = table.get_by_role("row").filter(has=page.get_by_role("cell", name=f"#{processes[0]}", exact=True))
    expect(selected).to_contain_text("1 pilihan aktif")
    page.once("dialog", lambda dialog: dialog.accept())
    selected.get_by_role("button").last.click()
    expect(selected).to_have_count(0)
    expect(table).to_contain_text(f"#{processes[1]}")
    page.reload()
    expect(table.get_by_role("row")).to_have_count(2)
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_text("Kelola riwayat", exact=True).click()
    page.get_by_role("button", name="Hapus Semua", exact=True).click()
    expect(page.get_by_text("Belum ada pemeriksaan tersimpan.", exact=False)).to_be_visible()
    page.reload()
    expect(page.get_by_text("Belum ada pemeriksaan tersimpan.", exact=False)).to_be_visible()
    assert httpx.get(f"{api}/history/processes").json() == []
    assert any(item["review_id"] == review for item in httpx.get(f"{api}/corrections/ready-pdpj").json())
    assert any(item["id"] == batch for item in httpx.get(f"{api}/corrections/{kind}/batches").json())


def test_running_history_is_retained_until_paused(page: Page, servers: tuple[str, str]) -> None:
    api = servers[1]
    review = prepare(api, candidates=1)
    batch = upload(api, "idpel_kosong", "NAMA,LAT,LON\nTarget,-6.2,106.8\n")
    response = httpx.post(f"{api}/corrections/idpel_kosong/checks", json={
        "batch_id": batch, "pdpj_review_id": review, "radius_meters": 10,
        "actor": "Uji Hapus", "request_key": "browser_delete_running", "incremental": True,
    })
    response.raise_for_status()
    check = response.json()
    page.goto("/history")
    row = page.get_by_role("table").get_by_role("row").filter(has=page.get_by_role("cell", name=f"#{check['process_id']}", exact=True))
    expect(row).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    row.get_by_role("button").last.click()
    expect(page.get_by_text("Hentikan sementara dan tunggu bagian aktif tersimpan", exact=False)).to_be_visible()
    expect(row).to_be_visible()
    response = httpx.post(f"{api}/corrections/idpel_kosong/checks/{check['process_id']}/pause", json={"run_id": check["latest_run"]["id"]})
    response.raise_for_status()
    page.once("dialog", lambda dialog: dialog.accept())
    row.get_by_role("button").last.click()
    expect(page.get_by_text("Belum ada pemeriksaan tersimpan.", exact=False)).to_be_visible()
