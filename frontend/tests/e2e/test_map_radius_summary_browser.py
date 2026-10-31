"""Global radius changes update whole-file counts and targets without selecting a row."""

import httpx
import pytest
from playwright.sync_api import Page, expect
from test_corrections_browser import prepare, upload


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_global_expansion_without_target_and_radius_specific_status_filters(
    page: Page, servers: tuple[str, str], kind: str
) -> None:
    api = servers[1]
    review = prepare(api, candidates=1)
    identity = "" if kind == "idpel_kosong" else "999"
    content = "IDPEL,NAMA,NOMOR_METER,LAT,LON\n"
    content += "".join(
        f"{identity},Luar {i},M{i + 100},-6.2,106.8011\n" for i in range(80)
    )
    content += f"{identity},Dekat,M900,-6.2,106.8\n{identity},Kosong,M901,,\n{identity},Benturan,M1,-6.2,106.8\n"
    batch = upload(api, kind, content)
    response = httpx.post(
        f"{api}/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review,
            "radius_meters": 100,
            "actor": "Petugas",
            "request_key": "radius_whole_file_start",
        },
        timeout=30,
    )
    response.raise_for_status()
    process = response.json()["process_id"]
    page.goto(f"/peta-koreksi?category={kind}&batch_id={batch}&process_id={process}")
    summary = page.get_by_role("region", name="Ringkasan radius peta", exact=True)

    def count(label: str, value: str) -> None:
        expect(
            summary.get_by_text(label, exact=True).locator("..").locator("dd")
        ).to_have_text(value)

    count("Baris tanpa kandidat", "80")
    count("Baris dengan kandidat", "1")
    count("Koordinat belum lengkap", "1")
    count("Benturan PDPJ", "1")
    status = page.get_by_label("Filter hasil peta", exact=True)
    status.select_option("no_candidates")
    table = page.get_by_role("region", name="Tabel target peta", exact=True)
    expect(table).to_contain_text("80 baris sesuai filter")
    expect(
        page.get_by_role("button", name="Tampilkan kandidat target", exact=True)
    ).to_be_disabled()
    radius_filter = page.get_by_label("Radius peta (meter)", exact=True)
    expect(radius_filter).to_have_attribute("max", "100")
    radius_filter.fill("150")
    expect(radius_filter).to_have_value("100")
    expect(page.get_by_role("alert")).to_contain_text("Filter radius maksimal 100 m")
    assert (
        len(httpx.get(f"{api}/corrections/{kind}/checks/{process}").json()["runs"]) == 1
    )
    page.get_by_label("Petugas peta", exact=True).fill("Petugas Radius")
    expand = page.get_by_role(
        "button", name="Perluas pemeriksaan dan tampilkan kandidat", exact=True
    )
    expansion_radius = page.get_by_label("Radius perluasan (meter)", exact=True)
    expansion_radius.fill("100")
    expect(expand).to_be_disabled()
    expansion_radius.fill("150")
    expect(radius_filter).to_have_value("100")
    expect(summary).to_contain_text("Radius 100 m · Versi 1")
    count("Baris tanpa kandidat", "80")
    expect(expand).to_be_enabled()
    expand.click()
    progress = page.get_by_role("region", name="Progres pemeriksaan koreksi")
    count("Baris tanpa kandidat", "0")
    count("Baris dengan kandidat", "81")
    expect(radius_filter).to_have_value("150")
    expect(radius_filter).to_have_attribute("max", "150")
    expect(progress).to_have_count(0)
    expect(summary.get_by_label("Perbandingan hasil radius")).to_contain_text(
        "80 baris yang sebelumnya tanpa kandidat kini mendapat kandidat"
    )
    expect(table).to_contain_text("0 baris sesuai filter")
    page.get_by_label("Radius peta (meter)", exact=True).fill("1")
    count("Baris tanpa kandidat", "80")
    count("Baris dengan kandidat", "1")
    expect(table).to_contain_text("80 baris sesuai filter")
    first = table.get_by_role("row").nth(1)
    expect(first).to_contain_text("Tanpa kandidat dalam radius")
    expect(first.locator("td").nth(4)).to_have_text("0")
    page.reload()
    count("Baris tanpa kandidat", "80")
    expect(page.get_by_label("Radius peta (meter)", exact=True)).to_have_value("1")
    expect(status).to_have_value("no_candidates")
    expect(table).to_contain_text("80 baris sesuai filter")
    assert (
        len(httpx.get(f"{api}/corrections/{kind}/checks/{process}").json()["runs"]) == 2
    )
    history = httpx.get(f"{api}/corrections/{kind}/checks/{process}/results/history")
    history.raise_for_status()
    assert history.json()["total"] == 0
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_initial_check_updates_summary_without_showing_expansion_panel(
    page: Page, servers: tuple[str, str]
) -> None:
    api = servers[1]
    review = prepare(api, candidates=1)
    batch = upload(api, "idpel_kosong", "NAMA,LAT,LON\n" + "Target,-6.2,106.8\n" * 3)
    response = httpx.post(
        f"{api}/corrections/idpel_kosong/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review,
            "radius_meters": 100,
            "actor": "Petugas",
            "request_key": "initial_map_summary",
            "incremental": True,
        },
    )
    response.raise_for_status()
    check = response.json()
    base = f"{api}/corrections/idpel_kosong/checks/{check['process_id']}"
    page.goto(
        f"/peta-koreksi?category=idpel_kosong&batch_id={batch}&process_id={check['process_id']}"
    )
    summary = page.get_by_role("region", name="Ringkasan radius peta", exact=True)
    progress = page.get_by_role(
        "region", name="Progres pemeriksaan koreksi", exact=True
    )
    expect(summary).to_contain_text("Hasil sementara: 0 dari 3 baris tersimpan.")
    expect(progress).to_have_count(0)
    run = check["latest_run"]

    def advance() -> dict:
        result = httpx.post(
            base + "/advance",
            json={
                "run_id": run["id"],
                "revision": run["processing"]["revision"],
                "chunk_size": 1,
            },
        )
        result.raise_for_status()
        return result.json()

    while run["processing"]["processed_rows"] == 0:
        run = advance()
    expect(summary).to_contain_text(
        "Hasil sementara: 1 dari 3 baris tersimpan.", timeout=15000
    )
    expect(progress).to_have_count(0)
    while run["status"] != "completed":
        run = advance()
    expect(
        summary.get_by_text("Baris tersimpan", exact=True).locator("..").locator("dd")
    ).to_have_text("3", timeout=15000)
    expect(summary.get_by_role("status")).to_have_count(0)
    expect(progress).to_have_count(0)
    page.reload()
    expect(summary).to_contain_text("Radius 100 m · Versi 1")
    expect(progress).to_have_count(0)
