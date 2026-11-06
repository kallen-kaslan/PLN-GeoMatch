"""Committed radius updates and account-based choices use real temporary records."""
import httpx
import pytest
from playwright.sync_api import Page, expect
from test_corrections_browser import prepare, upload
from workspace_controls import sign_in_map


def checked(response):
    response.raise_for_status()
    return response.json()


def prepare_analysis(api, kind):
    prepare(api, candidates=7)
    identity = "777" if kind == "idpel_tidak_ketemu" else ""
    content = "IDPEL,NAMA,LAT,LON\n" + f"{identity},Dekat,-6.2,106.8\n{identity},Jauh,-6.2,106.8004\n{identity},Koordinat kosong,,\n"
    if kind == "idpel_tidak_ketemu":
        content += "001,Sudah di PDPJ,,\n"
    batch = upload(api, kind, content)
    base = f"{api}/corrections/{kind}/radius-analyses"
    item = checked(httpx.post(base, json={"batch_id": batch, "actor": "Petugas Analisis", "request_key": "browser-map-analysis"}, timeout=30))
    for _ in range(80):
        if item["state"] == "ready":
            break
        item = checked(httpx.post(f"{base}/{item['id']}/advance", json={"revision": item["revision"]}, timeout=30))
    assert item["state"] == "ready"
    assert item["recommended_radius_meters"] == 45
    saved = checked(httpx.put(f"{base}/{item['id']}/radius", json={"revision": item["revision"], "radius_meters": 45}))
    process = checked(httpx.post(f"{base}/{item['id']}/search", json={"revision": saved["revision"], "request_key": "browser-map-search"}, timeout=30))["process_id"]
    path = f"{api}/corrections/{kind}/checks/{process}"
    run = checked(httpx.get(path + "/progress"))
    for _ in range(80):
        if run["status"] == "completed":
            break
        run = checked(httpx.post(path + "/advance", json={"run_id": run["id"], "revision": run["processing"]["revision"], "chunk_size": 10}, timeout=30))
    assert run["status"] == "completed"
    return batch, process


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_recommendation_draft_apply_reload_counts_and_account_choice(page: Page, servers, kind):
    api = servers[1]
    batch, process = prepare_analysis(api, kind)
    page.goto(f"/peta-koreksi?category={kind}&batch_id={batch}&process_id={process}")
    sign_in_map(page, "Akun Peta")
    page.evaluate("sessionStorage.setItem('pln_geomatch_correction_actor_' + new URLSearchParams(location.search).get('category'), 'Petugas Lama')")
    summary = page.get_by_role("region", name="Ringkasan radius peta", exact=True)
    controls = page.get_by_role("region", name="Kontrol radius", exact=True)
    radius = page.get_by_label("Radius peta (meter)", exact=True)
    expect(radius).to_have_value("45")
    expect(radius).to_have_attribute("max", "45")
    expect(controls).to_contain_text("Rekomendasi: 45 m")
    expect(page.get_by_label("Petugas peta", exact=True)).to_have_count(0)
    expect(page.get_by_label("Kategori peta", exact=True)).to_be_visible()
    expect(page.get_by_label("Berkas peta", exact=True)).to_be_visible()
    expect(page.get_by_label("Pemeriksaan peta", exact=True)).to_have_count(0)
    expect(page.get_by_label("Riwayat dan opsi peta", exact=True)).to_have_count(0)
    expect(page.get_by_label("Radius perluasan (meter)", exact=True)).to_have_count(0)
    def metric(label, value):
        expect(summary.get_by_text(label, exact=True).locator("..").locator("dd")).to_have_text(value)
    metric("Kandidat Ditemukan", "2")
    metric("Koordinat Bermasalah", "1")
    if kind == "idpel_tidak_ketemu":
        metric("IDPEL Sudah Ada di PDPJ", "1")
    requests = []
    writes = []
    page.on("request", lambda request: writes.append(request.url) if request.method != "GET" else None)
    page.on("request", lambda request: requests.append(request.url) if "/map-summary?" in request.url else None)
    page.get_by_role("slider", name="Atur radius peta", exact=True).press("Home")
    expect(radius).to_have_value("1")
    expect(controls).to_contain_text("Perubahan belum diterapkan")
    metric("Kandidat Ditemukan", "1")
    metric("Tanpa Kandidat", "1")
    expect(summary).to_contain_text("Pratinjau radius 1 m")
    expect(page.get_by_role("region", name="Pemetaan koreksi", exact=True)).to_contain_text("Radius peta aktif: 45 m")
    expect(page.get_by_role("table").get_by_role("row").nth(2)).to_contain_text("Kandidat ditemukan")
    assert any("radius_meters=1" in url for url in requests)
    page.get_by_role("button", name="Terapkan Radius", exact=True).click()
    metric("Kandidat Ditemukan", "1")
    metric("Tanpa Kandidat", "1")
    assert any("radius_meters=1" in url for url in requests)
    expect(page.get_by_role("region", name="Pemetaan koreksi", exact=True)).to_contain_text("Radius peta aktif: 1 m")
    assert not writes, "Preview and apply must only read stored results, never start a search"
    radius.fill("99")
    expect(page.get_by_role("button", name="Terapkan Radius", exact=True)).to_be_disabled()
    expect(controls.get_by_role("alert")).to_contain_text("maksimal 45 meter")
    radius.fill("20")
    page.reload()
    expect(radius).to_have_value("1")
    metric("Kandidat Ditemukan", "1")
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates.get_by_role("button", name="Pilih kandidat 1", exact=True)).to_be_disabled()
    sign_in_map(page, "Akun Peta")
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    detail = page.get_by_role("region", name="Detail target terpilih", exact=True)
    expect(detail).to_contain_text("Dipilih oleh Akun Peta")
    history = checked(httpx.get(f"{api}/corrections/{kind}/checks/{process}/results/history"))
    assert history["items"][0]["actor"] == "Akun Peta"
    assert controls.bounding_box()["y"] < summary.bounding_box()["y"]
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_role("slider", name="Atur radius peta", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_latest_completed_is_default_and_unfinished_version_remains_accessible(page: Page, servers):
    from test_correction_map_browser import setup_map
    api = servers[1]
    batch, process = setup_map(page, api, count=2)
    base = f"{api}/corrections/idpel_kosong/checks/{process}"
    old = checked(httpx.get(base))
    checked(httpx.post(base + "/retry", json={"latest_run_id": old["latest_run"]["id"], "radius_meters": 100, "actor": "Analisis", "request_key": "unfinished-map-default", "incremental": True}, timeout=30))
    page.goto(f"/peta-koreksi?category=idpel_kosong&batch_id={batch}&process_id={process}")
    expect(page.get_by_label("Radius peta (meter)", exact=True)).to_have_value("10")
    controls = page.get_by_role("region", name="Kontrol radius", exact=True)
    expect(controls).to_contain_text("Radius Tersimpan: 10 m")
    expect(page.get_by_label("Riwayat dan opsi peta", exact=True)).to_have_count(0)
    expect(page.get_by_label("Versi radius pemeriksaan", exact=True)).to_have_count(0)
