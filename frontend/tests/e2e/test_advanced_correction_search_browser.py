"""Find pinned identities beyond the radius, then save only a verified stored candidate."""

import re

import httpx
import pytest
from playwright.sync_api import expect
from test_corrections_browser import upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_advanced_finder_evidence_expansion_and_verified_unique_selection(
    page, servers, kind
):
    api = servers[1]
    upload(
        api,
        "dil",
        "IDPEL,NAMA,LAT,LON,NOMOR_METER_KWH,ALAMAT,NOMOR_GARDU\n001,PDPJ,-6.3,106.8,M001,PDPJ,G00\n002,Andi,-6.2,106.8,M002,Jalan A,G01\n003,Andika,-6.2,106.8,M003,Jalan B,G01\n004,Far customer,-6.205,106.8,M004,Jalan C,G02\n005,No location,,,M005,Jalan D,G02\n006,Excluded,-6.2,106.8,M006,Jalan E,G01\n",
    )
    pdpj = upload(api, "pdpj", "IDPEL,LAT,LON\n001,-6.3,106.8\n006,-6.2,106.8\n")
    review = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": pdpj}).json()
    httpx.post(
        f"{api}/pdpj/reviews/{review['id']}/complete",
        json={"revision": review["revision"], "actor": "ignored"},
    ).raise_for_status()
    batch = upload(
        api,
        kind,
        "IDPEL,NAMA,LAT,LON\n"
        + "".join(
            f"{'' if kind == 'idpel_kosong' else str(770 + index)},Target {index},-6.2,{106.8001 if index < 3 else 106.8004}\n"
            for index in (1, 2, 3)
        ),
    )
    checked = httpx.post(
        f"{api}/corrections/{kind}/checks",
        timeout=30,
        json={
            "batch_id": batch,
            "pdpj_review_id": review["id"],
            "radius_meters": 100,
            "actor": "ignored",
            "request_key": "advanced_browser_01",
        },
    )
    checked.raise_for_status()
    process = checked.json()["process_id"]
    upload(
        api,
        "dil",
        "IDPEL,NAMA,LAT,LON,NOMOR_METER_KWH\n007,New upload,-6.2,106.8,M007\n",
    )
    if kind == "idpel_tidak_ketemu":
        page.set_viewport_size({"width": 390, "height": 844})
    page.goto(
        f"/koreksi/pemilihan-otomatis?category={kind}&batch_id={batch}&process_id={process}"
    )
    panel = page.get_by_role("region", name="Pilihan kandidat otomatis", exact=True)
    comparison = panel.get_by_role(
        "region", name="Perbandingan kelompok terpilih", exact=True
    )
    finder = comparison.get_by_role(
        "region", name="Pencarian kandidat lanjutan", exact=True
    )

    def open_finder():
        panel.get_by_role(
            "button", name="Tinjau per kelompok koordinat / IDPEL", exact=True
        ).click()
        comparison.get_by_role(
            "button", name="Cari Kandidat Lanjutan", exact=True
        ).click()
        finder.get_by_label(
            "Cari kandidat lanjutan berdasarkan", exact=True
        ).select_option("meter")

    open_finder()

    def search(value):
        finder.get_by_label("Identitas untuk kandidat lanjutan", exact=True).fill(value)
        finder.get_by_role("button", name="Cari di master sisa", exact=True).click()

    search("M004")
    far = finder.get_by_role("article", name="Kandidat lanjutan IDPEL 004", exact=True)
    expect(far).to_be_visible()
    expect(
        far.get_by_role("link", name=re.compile("Tinjau perluasan pemeriksaan ke"))
    ).to_have_attribute("href", re.compile(r"expansion_radius_meters=\d+"))
    expect(
        far.get_by_role("button", name="Pilih hasil terverifikasi", exact=True)
    ).to_have_count(0)
    page_url = page.url
    expansion = far.get_by_role(
        "link", name=re.compile("Tinjau perluasan pemeriksaan ke")
    )
    proposed = re.search(
        r"expansion_radius_meters=(\d+)", expansion.get_attribute("href")
    ).group(1)
    expansion.click()
    expect(page.get_by_role("heading", name="Peta Koreksi", exact=True)).to_be_visible()
    expect(page.get_by_label("Radius perluasan (meter)", exact=True)).to_be_visible()
    expect(page.get_by_label("Radius perluasan (meter)", exact=True)).to_have_value(
        proposed
    )
    assert (
        httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()[
            "summary"
        ]["chosen_count"]
        == 0
    )
    page.goto(page_url)
    open_finder()
    search("M005")
    missing = finder.get_by_role(
        "article", name="Kandidat lanjutan IDPEL 005", exact=True
    )
    expect(missing.get_by_text("Jarak belum tersedia", exact=True)).to_be_visible()
    for identity in ("M006", "M007"):
        search(identity)
        expect(
            finder.get_by_role("status").filter(
                has_text="Tidak ada IDPEL tersedia yang cocok"
            )
        ).to_be_visible()
    search("M002")
    found = finder.get_by_role(
        "article", name="Kandidat lanjutan IDPEL 002", exact=True
    )
    expect(found).to_be_visible()
    expect(
        found.get_by_text("Nomor meter sumber sama dengan pencarian", exact=True)
    ).to_be_visible()
    found.get_by_text("Bukti identitas dari sumber (1)", exact=True).click()
    expect(
        found.locator("details").get_by_text(re.compile(r"dil.csv.*Baris 3"))
    ).to_be_visible()
    selected = found.get_by_role(
        "button", name="Pilih kandidat lanjutan IDPEL 002 untuk baris 2", exact=True
    )
    expect(selected).to_be_disabled()
    before = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()
    assert before["summary"]["chosen_count"] == 0
    comparison.get_by_label("Dasar verifikasi pilihan", exact=True).fill(
        "Meter M002 sesuai foto meter lapangan"
    )
    selected.click()
    expect(
        panel.get_by_role("status").filter(
            has_text="Pilihan IDPEL 002 untuk baris 2 tersimpan"
        )
    ).to_be_visible()
    expect(
        panel.get_by_text("Akan dipilih otomatis", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("1")
    results = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()
    assert (
        results["summary"]["chosen_count"] == results["summary"]["decision_events"] == 1
    )
    assert results["items"][0]["choice"]["candidate"]["fields"]["idpel"] == "002"
    assert (
        results["items"][0]["choice"]["reason"]
        == "Meter M002 sesuai foto meter lapangan"
    )
    panel.get_by_role(
        "button", name="Tinjau per kelompok koordinat / IDPEL", exact=True
    ).click()
    comparison.get_by_role("button", name="Cari Kandidat Lanjutan", exact=True).click()
    finder.get_by_label("Cari kandidat lanjutan berdasarkan", exact=True).select_option(
        "meter"
    )
    search("M002")
    expect(
        finder.get_by_role("status").filter(
            has_text="Tidak ada IDPEL tersedia yang cocok"
        )
    ).to_be_visible()
