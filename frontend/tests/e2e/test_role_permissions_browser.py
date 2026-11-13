"""Role controls use real sessions; auditors retain detail and spreadsheet access."""

import re

import httpx
import pytest
from conftest import TEST_PASSWORD
from playwright.sync_api import Page, expect
from test_authentication_browser import USER_PASSWORD, login_ui
from test_corrections_browser import prepare, upload


def switch_role(page: Page, api: httpx.Client, role: str) -> None:
    username = "permissions-" + role
    api.post(
        "/admin/users",
        json={"username": username, "password": USER_PASSWORD, "role": role,
              "admin_password": TEST_PASSWORD},
    ).raise_for_status()
    page.context.clear_cookies()
    page.goto("/login")
    login_ui(page, username, USER_PASSWORD)
    expect(page.get_by_role("button", name="Menu akun pengguna", exact=True)).to_be_visible()


@pytest.mark.parametrize("role", ["admin", "analis", "auditor"])
def test_upload_mapping_processing_and_history_controls_follow_role(
    page: Page, servers: tuple[str, str], authenticated_api: httpx.Client, role: str
) -> None:
    api = servers[1]
    review = prepare(api, candidates=1)
    batch = upload(api, "idpel_kosong", "IDPEL,NAMA,LAT,LON\n,Target,-6.2,106.8\n")
    check = authenticated_api.post(
        "/corrections/idpel_kosong/checks",
        json={"batch_id": batch, "pdpj_review_id": review, "radius_meters": 10, "actor": "test-admin",
              "request_key": "permissions-check", "incremental": True},
    )
    check.raise_for_status()
    process = check.json()["process_id"]
    authenticated_api.post(
        f"/corrections/idpel_kosong/checks/{process}/pause",
        json={"run_id": check.json()["latest_run"]["id"]},
    ).raise_for_status()
    pdpj_batch = upload(api, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    pdpj_review = authenticated_api.post(
        "/pdpj/reviews", json={"batch_id": pdpj_batch, "incremental": True}
    )
    pdpj_review.raise_for_status()
    authenticated_api.post(f"/pdpj/reviews/{pdpj_review.json()['id']}/pause").raise_for_status()
    pending = {}
    for kind in ("dil", "pdpj", "idpel_kosong"):
        response = authenticated_api.post(
            "/upload/", data={"dataset_type": kind},
            files={"file": ("pending.csv", b"IDPEL,LAT,LON\n,-6.2,106.8\n", "text/csv")},
        )
        response.raise_for_status()
        pending[kind] = response.json()["id"]

    switch_role(page, authenticated_api, role)
    write = role != "auditor"
    for route, upload_label, mapping_label in (
        ("/master/dil", "Unggah berkas", "Lanjutkan mapping"),
        (f"/pdpj?batch_id={pending['pdpj']}", "Unggah PDPJ", "Lanjutkan mapping PDPJ"),
        (f"/koreksi/idpel-kosong?batch_id={pending['idpel_kosong']}",
         "Unggah data koreksi", "Lanjutkan mapping koreksi"),
    ):
        page.goto(route)
        expect(page.get_by_label("Berkas sumber" if route.startswith("/master") else
                                 "Berkas PDPJ" if route.startswith("/pdpj") else "Berkas koreksi",
                                 exact=True)).to_be_visible()
        if route.startswith("/master"):
            page.get_by_label("Berkas sumber", exact=True).select_option(str(pending["dil"]))
        expect(page.get_by_role("button", name=upload_label, exact=True)).to_have_count(int(write))
        expect(page.get_by_role("button", name=mapping_label, exact=True)).to_have_count(int(write))
        if not write:
            expect(page.locator("input[type=file]")).to_have_count(0)

    page.goto(f"/pdpj?batch_id={pdpj_batch}")
    progress = page.get_by_role("region", name="Progres pemeriksaan PDPJ", exact=True)
    expect(progress).to_be_visible()
    expect(progress.get_by_role("button", name="Lanjutkan pemeriksaan", exact=True)).to_have_count(int(write))
    page.goto(f"/koreksi/idpel-kosong?batch_id={batch}&process_id={process}")
    progress = page.get_by_role("region", name="Progres pemeriksaan koreksi", exact=True)
    expect(progress).to_be_visible()
    expect(progress.get_by_role("button", name="Lanjutkan pemeriksaan koreksi", exact=True)).to_have_count(int(write))
    page.goto("/history")
    expect(page.get_by_role("table")).to_contain_text(str(process))
    if role == "admin":
        page.get_by_text("Kelola riwayat", exact=True).click()
    expect(page.get_by_role("button", name="Hapus Semua", exact=True)).to_have_count(int(role == "admin"))
    expect(page.locator('button[title="Hapus riwayat proses ini"]')).to_have_count(2 if role == "admin" else 0)
    expect(page.get_by_role("link", name="Input Manual & Matching", exact=True)).to_have_count(int(write))
    page.goto("/process")
    if write:
        expect(page.get_by_role("form", name="Input manual satu titik")).to_be_visible()
    else:
        expect(page.get_by_role("heading", name="Akses Ditolak", exact=True)).to_be_visible()


def test_auditor_can_read_details_candidates_results_and_download(
    page: Page, servers: tuple[str, str], authenticated_api: httpx.Client
) -> None:
    api = servers[1]
    review = prepare(api, candidates=1)
    batch = upload(api, "idpel_kosong", "IDPEL,NAMA,LAT,LON\n,Target,-6.2,106.8\n")
    response = authenticated_api.post(
        "/corrections/idpel_kosong/checks",
        json={"batch_id": batch, "pdpj_review_id": review, "radius_meters": 10, "actor": "test-admin",
              "request_key": "auditor-export"}, timeout=30,
    )
    response.raise_for_status()
    process = response.json()["process_id"]
    base = f"/corrections/idpel_kosong/checks/{process}"
    row = authenticated_api.get("/corrections/idpel_kosong/records", params={"process_id": process}).json()["items"][0]
    detail = authenticated_api.get(f"/corrections/idpel_kosong/records/{row['id']}", params={"process_id": process}).json()
    authenticated_api.post(
        base + f"/records/{row['id']}/choice",
        json={"generation": 1, "expected_revision": 0, "candidate_id": detail["candidates"][0]["id"],
              "request_key": "auditor-existing-choice", "reason": "Verifikasi", "actor": "test-admin"},
    ).raise_for_status()
    # An unfinished review with recommendations exercises read-only PDPJ detail.
    pdpj_batch = upload(api, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    pdpj_review = authenticated_api.post("/pdpj/reviews", json={"batch_id": pdpj_batch}).json()
    # Use a separate username because users persist between acceptance tests.
    authenticated_api.post(
        "/admin/users", json={"username": "permissions-reader", "password": USER_PASSWORD,
                              "role": "auditor", "admin_password": TEST_PASSWORD},
    ).raise_for_status()
    page.context.clear_cookies()
    page.goto("/login")
    login_ui(page, "permissions-reader", USER_PASSWORD)
    expect(page.get_by_role("button", name="Menu akun pengguna", exact=True)).to_be_visible()
    writes = []
    page.on("request", lambda request: writes.append(request.url) if request.method in {"POST", "PATCH", "PUT", "DELETE"} else None)
    page.goto(f"/pdpj?batch_id={pdpj_batch}&review_id={pdpj_review['id']}")
    page.get_by_role("button", name="Detail PDPJ baris 2", exact=True).click()
    expect(page.get_by_role("region", name="Detail pemeriksaan PDPJ", exact=True)).to_contain_text("Data awal dan data saat ini")
    expect(page.get_by_role("button", name=re.compile("Terapkan|Simpan|Setujui"))).to_have_count(0)
    expect(page.get_by_text("Isi atau perbaiki data secara manual", exact=True)).to_have_count(0)
    page.goto(f"/peta-koreksi?category=idpel_kosong&batch_id={batch}&process_id={process}&record_id={row['id']}")
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates.get_by_role("article")).to_have_count(1)
    expect(candidates.get_by_role("button", name=re.compile("Pilih kandidat|Kandidat terpilih"))).to_have_count(0)
    expect(page.get_by_role("button", name="Batalkan pilihan", exact=True)).to_have_count(0)
    expect(page.get_by_label("Perluasan radius seluruh berkas", exact=True)).to_have_count(0)
    page.goto(f"/result?category=idpel_kosong&process_id={process}")
    expect(page.get_by_role("region", name="Daftar hasil koreksi", exact=True)).to_contain_text("002")
    for label in ("Ekspor hasil XLSX", "Unduh riwayat XLSX"):
        with page.expect_download() as download:
            page.get_by_role("button", name=label, exact=True).click()
        assert download.value.suggested_filename.endswith(".xlsx")
        assert download.value.failure() is None
    assert writes == []


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_auditor_radius_filter_stays_read_only_with_direct_expansion_link(
    page: Page, servers: tuple[str, str], authenticated_api: httpx.Client, kind: str
) -> None:
    review = prepare(servers[1], candidates=1)
    identity = "" if kind == "idpel_kosong" else "777"
    batch = upload(servers[1], kind, f"IDPEL,NAMA,LAT,LON\n{identity},Target,-6.2,106.8\n")
    response = authenticated_api.post(
        f"/corrections/{kind}/checks",
        json={"batch_id": batch, "pdpj_review_id": review, "radius_meters": 10,
              "actor": "test-admin", "request_key": "auditor-radius-filter"}, timeout=30,
    )
    response.raise_for_status()
    process = response.json()["process_id"]
    username = "radius-" + kind
    authenticated_api.post(
        "/admin/users", json={"username": username, "password": USER_PASSWORD,
                              "role": "auditor", "admin_password": TEST_PASSWORD},
    ).raise_for_status()
    page.context.clear_cookies()
    page.goto("/login")
    login_ui(page, username, USER_PASSWORD)
    expect(page.get_by_role("button", name="Menu akun pengguna", exact=True)).to_be_visible()
    writes = []
    page.on("request", lambda request: writes.append(request.url) if request.method in {"POST", "PUT", "PATCH", "DELETE"} else None)
    url = (f"/peta-koreksi?category={kind}&batch_id={batch}&process_id={process}"
           "&radius_meters=1000&expansion_radius_meters=1000")
    for width in (1440, 390):
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(url)
        radius = page.get_by_label("Radius peta (meter)", exact=True)
        expect(radius).to_have_value("10")
        expect(radius).to_be_enabled()
        expect(page.get_by_label("Perluasan radius seluruh berkas", exact=True)).to_have_count(0)
        expect(page.get_by_label("Radius perluasan (meter)", exact=True)).to_have_count(0)
        expect(page.get_by_role("button", name="Perluas pemeriksaan dan tampilkan kandidat", exact=True)).to_have_count(0)
        expect(page.get_by_role("button", name="Perbarui ringkasan radius", exact=True)).to_have_count(0)
        radius.fill("5")
        expect(page.get_by_role("region", name="Ringkasan radius peta", exact=True)).to_contain_text("Radius 5 m")
        radius.fill("1000")
        expect(radius).to_have_value("10")
        expect(page.get_by_role("alert").filter(has_text="Auditor hanya dapat melihat kandidat")).to_be_visible()
        expect(page.get_by_text(re.compile("Gunakan Radius perluasan"))).to_have_count(0)
        page.reload()
        expect(radius).to_have_value("10")
        expect(page.get_by_role("button", name=re.compile("Perluas pemeriksaan"))).to_have_count(0)
        expect(page.get_by_role("button", name="Perbarui ringkasan radius", exact=True)).to_have_count(0)
    assert writes == []
    saved = authenticated_api.get(f"/corrections/{kind}/checks/{process}").json()
    assert len(saved["runs"]) == 1
    assert saved["latest_run"]["radius_meters"] == 10
