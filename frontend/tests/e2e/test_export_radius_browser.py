"""Export uses the visible filter and original target OBJECTID without changing choices."""

from pathlib import Path

import httpx
import pytest
from openpyxl import load_workbook
from playwright.sync_api import Page, expect
from test_corrections_browser import prepare, upload
from workspace_controls import open_radius_controls


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_map_and_results_export_original_objectid_filtered_radius_and_real_distance(
    page: Page,
    servers: tuple[str, str],
    tmp_path: Path,
    kind: str,
) -> None:
    api = servers[1]
    review = prepare(api, candidates=2)
    batch = upload(
        api,
        kind,
        "OBJECTID,IDPEL,NAMA,LAT,LON\n"
        + f"0001,{'' if kind == 'idpel_kosong' else '777'},Target near,-6.2,106.8\n"
        + f"0002,{'' if kind == 'idpel_kosong' else '778'},Target far,-6.2,106.8\n",
    )
    checked = httpx.post(
        f"{api}/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review,
            "radius_meters": 250,
            "actor": "ignored",
            "request_key": "export_radius_browser",
        },
    )
    checked.raise_for_status()
    process = checked.json()["process_id"]
    base = f"{api}/corrections/{kind}/checks/{process}"
    rows = httpx.get(
        f"{api}/corrections/{kind}/records", params={"process_id": process}
    ).json()["items"]
    distances = []
    for row, identity in zip(rows, ("002", "099")):
        detail = httpx.get(
            f"{api}/corrections/{kind}/records/{row['id']}",
            params={"process_id": process},
        ).json()
        candidate = next(
            item for item in detail["candidates"] if item["fields"]["idpel"] == identity
        )
        distances.append(candidate["distance_meters"])
        httpx.post(
            base + f"/records/{row['id']}/choice",
            json={
                "generation": 1,
                "expected_revision": 0,
                "candidate_id": candidate["id"],
                "actor": "ignored",
                "reason": "",
                "request_key": f"export_radius_choice_{row['id']}",
            },
        ).raise_for_status()
    assert distances[0] <= 50 < distances[1] < 250

    def verify_download(button: str, radius: int, identities: list[str]) -> None:
        with page.expect_download() as downloaded:
            page.get_by_role("button", name=button, exact=True).click()
        assert downloaded.value.suggested_filename.endswith(f"radius_{radius}m_v1.xlsx")
        path = tmp_path / f"export-{radius}-{len(identities)}.xlsx"
        downloaded.value.save_as(path)
        book = load_workbook(path)
        assert book.sheetnames == ["Hasil Koreksi"]
        values = list(book.active.values)
        assert values[0][0] == "objectid"
        assert len(values[0]) == 12
        exported = [dict(zip(values[0], row)) for row in values[1:]]
        assert [row["objectid"] for row in exported] == identities
        assert all(row["radius_pemeriksaan_meter"] == radius for row in exported)
        for row, distance in zip(exported, distances):
            assert row["jarak_kandidat_meter"] == pytest.approx(distance)
        assert book.active["A2"].data_type == "s"
        book.close()

    page.goto(f"/peta-koreksi?category={kind}&batch_id={batch}&process_id={process}")
    verify_download("Unduh hasil radius 250 m XLSX", 250, ["0001", "0002"])
    open_radius_controls(page)
    page.get_by_label("Radius peta (meter)", exact=True).fill("50")
    verify_download("Unduh hasil radius 50 m XLSX", 50, ["0001"])
    page.get_by_role("link", name="Lihat Hasil Koreksi", exact=True).click()
    expect(
        page.get_by_label("Filter radius hasil ekspor (meter)", exact=True)
    ).to_have_value("50")
    results = page.get_by_role("region", name="Daftar hasil koreksi", exact=True)
    expect(results.get_by_role("row")).to_have_count(2)
    verify_download("Ekspor hasil XLSX", 50, ["0001"])
    page.reload()
    expect(
        page.get_by_label("Filter radius hasil ekspor (meter)", exact=True)
    ).to_have_value("50")
    page.get_by_label("Filter radius hasil ekspor (meter)", exact=True).fill("250")
    expect(results.get_by_role("row")).to_have_count(3)
    verify_download("Ekspor hasil XLSX", 250, ["0001", "0002"])
    # A smaller export filter never cancels the saved choice outside it.
    choice = httpx.get(base + f"/records/{rows[1]['id']}/choice").json()
    assert choice["current"]["candidate"]["fields"]["idpel"] == "099"
