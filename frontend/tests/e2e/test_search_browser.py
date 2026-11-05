"""Search inputs debounce requests, preserve paging, and filter the expected fields."""

import re
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from playwright.sync_api import Page, expect
from test_correction_map_browser import setup_map
from test_corrections_browser import prepare, upload


def test_master_search_debounces_prepares_and_preserves_pagination(
    page: Page, servers: tuple[str, str],
) -> None:
    upload(servers[1], "dil", "IDPEL,NAMA,LAT,LON\n" + "".join(
        f"{i:06},Original {i:04},-6.2,106.8\n" for i in range(1, 1002)
    ) + "999999,SearchNeedle,-6.2,106.8\n")
    page.goto("/master/dil")
    field = page.get_by_role("searchbox", name="Cari data master", exact=True)
    expect(page.get_by_role("cell", name="000001", exact=False)).to_be_visible()
    requests = []
    page.on("request", lambda r: requests.append(parse_qs(urlparse(r.url).query).get("q", [""])[0])
            if "/master/dil/records?" in r.url else None)
    field.press_sequentially("Needle", delay=30)
    expect(page.get_by_text("Menyiapkan pencarian pada data tersimpan", exact=False)).to_be_visible()
    expect(page.get_by_role("cell", name="999999 SearchNeedle", exact=False)).to_be_visible(timeout=15000)
    assert set(requests) == {"Needle"}, requests
    field.fill("Original")
    expect(page.get_by_label("Navigasi halaman master")).to_contain_text("1.001 baris")
    page.get_by_role("button", name="Halaman berikutnya", exact=True).click()
    expect(page.get_by_role("cell", name="000026", exact=False)).to_be_visible()
    field.fill("Needle")
    expect(page.get_by_role("cell", name="999999 SearchNeedle", exact=False)).to_be_visible()
    expect(page.get_by_label("Nomor halaman master", exact=True)).to_have_value("1")
    expect(page.get_by_role("button", name="Halaman berikutnya", exact=True)).to_be_disabled()
    field.fill("")
    expect(page.get_by_label("Navigasi halaman master")).to_contain_text("1.002 baris")


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_correction_search_filters_and_clears(
    page: Page, servers: tuple[str, str], kind: str,
) -> None:
    identity = "" if kind == "idpel_kosong" else "900"
    batch = upload(servers[1], kind, "IDPEL,NAMA,LAT,LON\n" +
                   f"{identity},Needle One,-6.2,106.8\n{identity},Needle Two,-6.2,106.8\n{identity},Other,-6.2,106.8\n")
    page.goto(f"/koreksi/{kind.replace('_', '-')}?batch_id={batch}")
    field = page.get_by_role("searchbox", name="Cari data koreksi", exact=True)
    field.fill("needle")
    expect(page.get_by_label("Navigasi halaman koreksi")).to_contain_text("2 baris")
    expect(page.get_by_role("cell", name=re.compile("Needle One"))).to_be_visible()
    expect(page.get_by_role("cell", name="Other", exact=False)).not_to_be_visible()
    field.fill("")
    expect(page.get_by_label("Navigasi halaman koreksi")).to_contain_text("3 baris")


def test_pdpj_search_includes_kwh_meter_and_clear(
    page: Page, servers: tuple[str, str],
) -> None:
    prepare(servers[1])
    batch = upload(servers[1], "pdpj", "IDPEL,NAMA,LAT,LON,NOAGENDA,NOMOR_METER_KWH\n001,Needle PDPJ,-6.2,106.8,AGENDA-OTHER,KWH-98765\n")
    review = httpx.post(f"{servers[1]}/pdpj/reviews", json={"batch_id": batch}).json()
    finished = httpx.post(f"{servers[1]}/pdpj/reviews/{review['id']}/complete", json={"revision": review["revision"], "actor": "Search test"})
    finished.raise_for_status()
    page.goto(f"/pdpj?batch_id={batch}&review_id={review['id']}")
    field = page.get_by_role("searchbox", name="Cari data PDPJ", exact=True)
    field.fill("98765")
    expect(page.get_by_role("cell", name=re.compile("Needle PDPJ"))).to_be_visible()
    field.fill("missing-search-value")
    expect(page.get_by_text("Tidak ada baris sesuai filter.", exact=True)).to_be_visible()
    field.fill("")
    expect(page.get_by_role("cell", name=re.compile("Needle PDPJ"))).to_be_visible()


def test_map_and_saved_result_search_keep_the_selected_scope(
    page: Page, servers: tuple[str, str],
) -> None:
    _batch, process = setup_map(page, servers[1], count=12)
    field = page.get_by_role("searchbox", name="Cari target peta", exact=True)
    field.fill("Target 12")
    expect(page.get_by_role("button", name="Pilih target baris 13", exact=True)).to_be_visible()
    expect(page.get_by_label("Navigasi halaman peta")).to_contain_text("1 baris")
    field.fill("")
    expect(page.get_by_label("Navigasi halaman peta")).to_contain_text("13 baris")
    rows = httpx.get(f"{servers[1]}/corrections/idpel_kosong/records", params={"process_id": process}).json()["items"]
    record = rows[0]["id"]
    detail = httpx.get(f"{servers[1]}/corrections/idpel_kosong/records/{record}", params={"process_id": process}).json()
    response = httpx.post(f"{servers[1]}/corrections/idpel_kosong/checks/{process}/records/{record}/choice", json={
        "generation": 1, "expected_revision": 0, "candidate_id": detail["candidates"][0]["id"],
        "actor": "Petugas Pencarian", "reason": "Uji pencarian", "request_key": "search_browser_choice",
    })
    response.raise_for_status()
    page.goto(f"/result?category=idpel_kosong&process_id={process}")
    field = page.get_by_role("searchbox", name="Cari hasil koreksi", exact=True)
    field.fill("Petugas Pencarian")
    expect(page.get_by_role("cell", name=re.compile("Petugas Pencarian"))).to_be_visible()
    field.fill("missing-search-value")
    expect(page.get_by_text("Tidak ada hasil sesuai filter.", exact=False)).to_be_visible()
    field.fill("")
    expect(page.get_by_role("cell", name=re.compile("Petugas Pencarian"))).to_be_visible()


def test_admin_local_search_matches_username_and_email(page: Page) -> None:
    page.goto("/login")
    page.get_by_label("Username", exact=True).fill("admin")
    page.get_by_label("Password", exact=True).fill("test-password")
    page.get_by_role("button", name="Masuk", exact=True).click()
    page.get_by_role("link", name="Manajemen Pengguna", exact=True).click()
    field = page.get_by_placeholder("Cari username atau email...")
    field.fill("AUDIT@PLN")
    expect(page.get_by_role("cell", name="auditor1", exact=True)).to_be_visible()
    expect(page.get_by_role("cell", name="petugas", exact=True)).not_to_be_visible()
    field.fill("")
    expect(page.get_by_role("cell", name="petugas", exact=True)).to_be_visible()
