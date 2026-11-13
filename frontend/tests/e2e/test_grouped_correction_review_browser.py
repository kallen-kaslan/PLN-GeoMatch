"""Resolve a shared-coordinate group with evidence, then reuse released candidates."""

import httpx
import pytest
from playwright.sync_api import expect
from test_corrections_browser import upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_group_review_verifies_one_choice_refreshes_preview_and_keeps_idpel_unique(
    page, servers, kind
):
    api = servers[1]
    upload(
        api,
        "dil",
        "IDPEL,NAMA,LAT,LON,NOMOR_METER_KWH,ALAMAT,NOMOR_GARDU\n001,PDPJ,-6.3,106.8,M001,PDPJ,G0\n002,Pelanggan A,-6.2,106.8,M002,Jalan A,G1\n003,Pelanggan B,-6.2,106.8,M003,Jalan B,G1\n",
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
        "OBJECTID,IDPEL,NAMA,LAT,LON,ALAMAT\n"
        + "".join(
            f"00{index},{'' if kind == 'idpel_kosong' else str(770 + index)},Target {index},-6.2,{106.8001 if index < 3 else 106.8004},Jalan Target {index}\n"
            for index in (1, 2, 3)
        ),
    )
    checked = httpx.post(
        f"{api}/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review["id"],
            "radius_meters": 100,
            "actor": "ignored",
            "request_key": "group_review_browser",
        },
    )
    checked.raise_for_status()
    process = checked.json()["process_id"]
    if kind == "idpel_tidak_ketemu":
        page.set_viewport_size({"width": 390, "height": 844})
    page.goto(
        f"/koreksi/pemilihan-otomatis?category={kind}&batch_id={batch}&process_id={process}"
    )
    panel = page.get_by_role("region", name="Pilihan kandidat otomatis", exact=True)
    pending = (
        panel.get_by_text("Belum dipilih / perlu tinjauan", exact=True)
        .locator("..")
        .get_by_role("definition")
    )
    expect(pending).to_have_text("3")
    panel.get_by_role(
        "button", name="Tinjau per kelompok koordinat / IDPEL", exact=True
    ).click()
    groups = panel.get_by_role(
        "region", name="Tinjauan kelompok koordinat dan IDPEL", exact=True
    )
    expect(
        groups.get_by_text(
            "3 target dalam 1 kelompok. Satu target dihitung satu kali.", exact=True
        )
    ).to_be_visible()
    comparison = groups.get_by_role(
        "region", name="Perbandingan kelompok terpilih", exact=True
    )
    expect(
        comparison.get_by_role(
            "heading", name="Bandingkan 3 target dan 2 IDPEL", exact=True
        )
    ).to_be_visible()
    expect(comparison.get_by_text("M002", exact=True)).to_be_visible()
    expect(comparison.get_by_text("Jalan B", exact=True)).to_be_visible()
    chosen = comparison.get_by_role(
        "button", name="Pilih IDPEL 002 untuk baris 2", exact=True
    )
    expect(chosen).to_be_disabled()
    comparison.get_by_label("Dasar verifikasi pilihan", exact=True).fill(
        "Meter M002 sesuai bukti lapangan"
    )
    expect(chosen).to_be_enabled()
    chosen.click()
    expect(
        panel.get_by_role("status").filter(
            has_text="Pilihan IDPEL 002 untuk baris 2 tersimpan"
        )
    ).to_be_visible()
    expect(pending).to_have_text("1")
    expect(
        panel.get_by_text("Akan dipilih otomatis", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("1")
    rows = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()
    assert rows["summary"]["chosen_count"] == 1
    assert rows["items"][0]["choice"]["reason"] == "Meter M002 sesuai bukti lapangan"
    assert rows["items"][0]["choice"]["actor"] == "test-admin"
    with page.expect_download():
        panel.get_by_role("button", name="Simpan & ekspor XLSX", exact=True).click()
    panel.get_by_role("button", name="Pratinjau pilihan otomatis", exact=True).click()
    expect(
        panel.get_by_text("Keputusan tersimpan dipertahankan", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("2")
    panel.get_by_role(
        "button", name="Tinjau per kelompok koordinat / IDPEL", exact=True
    ).click()
    expect(
        groups.get_by_text(
            "1 target dalam 1 kelompok. Satu target dihitung satu kali.", exact=True
        )
    ).to_be_visible()
    comparison.get_by_label("Dasar verifikasi pilihan", exact=True).fill(
        "Tinjau calon berikutnya"
    )
    expect(
        comparison.get_by_role(
            "button", name="Pilih IDPEL 002 untuk baris 4", exact=True
        )
    ).to_be_disabled()
    expect(
        comparison.get_by_role(
            "button", name="Pilih IDPEL 003 untuk baris 4", exact=True
        )
    ).to_be_disabled()
    expect(comparison.get_by_text("Dipakai baris 2", exact=True)).to_be_visible()
    expect(comparison.get_by_text("Dipakai baris 3", exact=True)).to_be_visible()
    results = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()
    assert (
        results["summary"]["chosen_count"] == results["summary"]["decision_events"] == 2
    )
    assert (
        len({row["choice"]["candidate"]["fields"]["idpel"] for row in results["items"]})
        == 2
    )
