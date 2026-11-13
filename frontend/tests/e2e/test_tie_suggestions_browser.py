"""Ambiguous pairs remain proposals until verified with evidence in the map."""

import httpx
import pytest
from openpyxl import load_workbook
from playwright.sync_api import expect
from test_corrections_browser import prepare, upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_suggestions_download_verify_map_and_refresh_unique_pairs(
    page, servers, tmp_path, kind
):
    api = servers[1]
    duplicate_keys = []
    page.on(
        "console",
        lambda message: (
            duplicate_keys.append(message.text) if "same key" in message.text else None
        ),
    )
    review = prepare(api, candidates=2)
    batch = upload(
        api,
        kind,
        "OBJECTID,IDPEL,NAMA,LAT,LON\n"
        + "".join(
            f"00{index},{'' if kind == 'idpel_kosong' else str(770 + index)},Target {index},-6.2,106.8\n"
            for index in (1, 2, 3)
        ),
    )
    checked = httpx.post(
        f"{api}/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review,
            "radius_meters": 10,
            "actor": "ignored",
            "request_key": "tie_suggestion_browser",
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
    mode = panel.get_by_label("Penanganan jarak sama", exact=True)
    expect(mode).to_have_value("review")
    mode.select_option("suggest")
    proposals = panel.get_by_role(
        "region", name="Usulan pasangan jarak sama", exact=True
    )
    expect(
        proposals.get_by_role(
            "heading", name="Usulan pasangan untuk jarak sama: 2 target", exact=True
        )
    ).to_be_visible()
    expect(
        panel.get_by_text("Belum mendapat pasangan", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("1")
    proposals.get_by_text("Tinjau target tanpa pasangan (1)", exact=True).click()
    expect(
        proposals.get_by_role("link", name="Tinjau target baris 4", exact=True)
    ).to_be_visible()
    follow_up = proposals.get_by_role(
        "region", name="Penanganan target tanpa pasangan", exact=True
    )
    follow_up.get_by_role("button", name="Cari kandidat tambahan", exact=True).click()
    expect(
        follow_up.get_by_role("status").filter(
            has_text="Radius 500 m: 1 target mendapat kandidat tambahan, 0 target belum mendapat pasangan."
        )
    ).to_be_visible()
    expect(follow_up.get_by_text("IDPEL 099", exact=True)).to_be_visible()
    with page.expect_download() as additional:
        follow_up.get_by_role(
            "button", name="Unduh Usulan Lanjutan XLSX", exact=True
        ).click()
    additional_path = tmp_path / additional.value.suggested_filename
    additional.value.save_as(additional_path)
    additional_book = load_workbook(additional_path)
    assert additional_book.sheetnames == ["Usulan Lanjutan"]
    assert additional_book.active["A2"].value == "003"
    assert additional_book.active["C2"].value == "099"
    assert additional_book.active["M2"].value == "Perlu verifikasi"
    assert additional_book.active["O2"].value == 10
    follow_up.get_by_role("button", name="Cari identitas baris 4", exact=True).click()
    follow_up.get_by_role("button", name="Cari Kandidat Lanjutan", exact=True).click()
    follow_up.get_by_label(
        "Cari kandidat lanjutan berdasarkan", exact=True
    ).select_option("idpel")
    follow_up.get_by_label("Identitas untuk kandidat lanjutan", exact=True).fill("099")
    follow_up.get_by_role("button", name="Cari di master sisa", exact=True).click()
    expect(
        follow_up.get_by_role("article", name="Kandidat lanjutan IDPEL 099", exact=True)
    ).to_be_visible()
    follow_up.get_by_role(
        "link", name="Tinjau perluasan baris 4 ke 57 m", exact=True
    ).click()
    expect(
        page.get_by_label("Radius perluasan (meter)", exact=True)
    ).to_have_value("57")
    expect(
        page.get_by_role("status").filter(
            has_text="Usulan lanjutan IDPEL 099 belum tersedia"
        )
    ).to_be_visible()
    assert (
        httpx.get(f"{api}/corrections/{kind}/checks/{process}").json()["latest_run"][
            "generation"
        ]
        == 1
    )
    page.go_back()
    page.reload()
    expect(mode).to_have_value("suggest")
    with page.expect_download() as download:
        proposals.get_by_role("button", name="Unduh Usulan XLSX", exact=True).click()
    path = tmp_path / download.value.suggested_filename
    download.value.save_as(path)
    expect(proposals).to_have_count(1)
    book = load_workbook(path)
    assert book.sheetnames == ["Usulan Jarak Sama"]
    sheet = book.active
    assert [cell.value for cell in sheet[1]][-2:] == ["Status Usulan", "Baris Target"]
    assert {sheet.cell(row, 13).value for row in (2, 3)} == {"Perlu verifikasi"}
    assert {sheet.cell(row, 3).value for row in (2, 3)} == {"002", "003"}
    assert {sheet.cell(row, 1).value for row in (2, 3)} == {"001", "002"}
    before = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()
    assert before["summary"]["decision_events"] == 0
    proposals.get_by_role("link", name="Verifikasi usulan baris 2", exact=True).click()
    expect(page.get_by_role("heading", name="Peta Koreksi", exact=True)).to_be_visible()
    expect(
        page.get_by_role("status").filter(has_text="Usulan IDPEL 002")
    ).to_be_visible()
    candidate = page.get_by_role("article", name="Kandidat peta 1", exact=True)
    pick = candidate.get_by_role("button", name="Pilih kandidat 1", exact=True)
    expect(pick).to_be_disabled()
    page.get_by_label("Alasan perubahan pilihan", exact=True).fill(
        "Identitas meter 002 sesuai bukti lapangan"
    )
    expect(pick).to_be_enabled()
    pick.click()
    expect(
        candidate.get_by_role("button", name="Kandidat terpilih", exact=True)
    ).to_be_visible()
    page.get_by_role("link", name="Kembali ke usulan pasangan", exact=True).click()
    expect(mode).to_have_value("suggest")
    expect(
        proposals.get_by_role(
            "heading", name="Usulan pasangan untuk jarak sama: 1 target", exact=True
        )
    ).to_be_visible()
    expect(
        panel.get_by_text("Keputusan tersimpan dipertahankan", exact=True)
        .locator("..")
        .get_by_role("definition")
    ).to_have_text("1")
    expect(proposals.get_by_role("cell", name="003", exact=True)).to_be_visible()
    expect(proposals.get_by_role("cell", name="002", exact=True)).to_have_count(0)
    panel.get_by_role(
        "button", name="Tinjau per kelompok koordinat / IDPEL", exact=True
    ).click()
    groups = panel.get_by_role(
        "region", name="Tinjauan kelompok koordinat dan IDPEL", exact=True
    )
    expect(groups.get_by_text("Usulan sistem:", exact=False)).to_contain_text(
        "IDPEL 003"
    )
    after = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results").json()
    assert after["summary"]["chosen_count"] == 1
    assert after["summary"]["decision_events"] == 1
    choice = after["items"][0]["choice"]
    assert choice["candidate"]["fields"]["idpel"] == "002"
    assert choice["actor"] == "test-admin"
    assert choice["reason"] == "Identitas meter 002 sesuai bukti lapangan"
    assert not duplicate_keys
