"""Use saved correction rows in the map while the same check remains resumable."""

import httpx
import pytest
from playwright.sync_api import Page, expect

from test_corrections_browser import prepare, upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
@pytest.mark.parametrize("paused", [False, True])
def test_partial_map_choice_survives_more_saved_rows_and_completion(
    page: Page, servers: tuple[str, str], kind: str, paused: bool
) -> None:
    api = servers[1]
    review = prepare(api, candidates=2)
    batch = upload(
        api, kind, "IDPEL,NAMA,LAT,LON\n"
        + "".join(f"{700 + i if kind == 'idpel_tidak_ketemu' else ''},Target {i},-6.2,106.8\n" for i in range(5)),
    )
    response = httpx.post(f"{api}/corrections/{kind}/checks", json={
        "batch_id": batch, "pdpj_review_id": review, "radius_meters": 10,
        "actor": "Petugas", "request_key": "partial_map_browser", "incremental": True,
    })
    response.raise_for_status()
    check = response.json()
    process = check["process_id"]
    base = f"{api}/corrections/{kind}/checks/{process}"

    def advance(run: dict) -> dict:
        result = httpx.post(base + "/advance", json={"run_id": run["id"],
            "revision": run["processing"]["revision"], "chunk_size": 2})
        result.raise_for_status()
        return result.json()

    run = advance(advance(check["latest_run"]))
    assert run["processing"]["processed_rows"] == 2
    if paused:
        result = httpx.post(base + "/pause", json={"run_id": run["id"]})
        result.raise_for_status()
    slug = kind.replace("_", "-")
    page.goto(f"/koreksi/{slug}?batch_id={batch}&process_id={process}")
    page.get_by_role("link", name="Buka Peta Koreksi", exact=True).click()
    expect(page.get_by_text("2 dari 5 baris sudah tersimpan", exact=False)).to_be_visible()
    table = page.get_by_role("region", name="Tabel target peta", exact=True)
    expect(table.get_by_role("button", name="Pilih target baris 2", exact=True)).to_be_visible()
    expect(table.get_by_role("button", name="Pilih target baris 4", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    page.get_by_label("Petugas peta", exact=True).fill("Petugas Peta Bertahap")
    page.get_by_label("Radius peta (meter)", exact=True).fill("100")
    expect(page.get_by_role("button", name="Perluas pemeriksaan dan tampilkan kandidat", exact=True)).to_be_disabled()
    page.get_by_label("Radius peta (meter)", exact=True).fill("10")
    page.get_by_role("button", name="Tampilkan kandidat target", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("2 kandidat tersimpan")
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    detail = page.get_by_role("region", name="Detail target terpilih", exact=True)
    expect(detail).to_contain_text("Pilihan aktif: 002")
    source_rows = httpx.get(f"{api}/corrections/{kind}/records", params={"process_id": process}).json()["items"]
    choice_url = base + f"/records/{source_rows[0]['id']}/choice"
    choice = httpx.get(choice_url).json()
    assert choice["revision"] == 1
    assert httpx.get(base).json()["current_generation"] == 0
    if paused:
        result = httpx.post(base + "/resume", json={"run_id": run["id"]})
        result.raise_for_status()
        run = result.json()
    run = advance(run)
    expect(page.get_by_text("4 dari 5 baris sudah tersimpan", exact=False)).to_be_visible(timeout=15000)
    expect(table.get_by_role("button", name="Pilih target baris 4", exact=True)).to_be_visible()
    expect(detail).to_contain_text("Pilihan aktif: 002")
    page.get_by_role("link", name="Buka data dan riwayat pemeriksaan", exact=True).click()
    page.get_by_role("button", name="Lanjutkan pemeriksaan koreksi", exact=True).click()
    expect(page.get_by_role("dialog", name="Pemeriksaan koreksi selesai", exact=True)).to_be_visible(timeout=20000)
    page.get_by_role("button", name="Lihat hasil pemeriksaan", exact=True).click()
    page.get_by_role("link", name="Buka Peta Koreksi", exact=True).click()
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    expect(detail).to_contain_text("Pilihan aktif: 002")
    assert httpx.get(choice_url).json() == choice
    assert httpx.get(base).json()["latest_run"]["id"] == run["id"]
