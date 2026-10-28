"""Use approved partial PDPJ data in corrections, then resume the original review."""

import httpx
from playwright.sync_api import Page, expect

from test_corrections_browser import launch, upload


def test_approve_partial_correct_and_resume_without_changing_old_reference(
    page: Page, servers: tuple[str, str],
) -> None:
    api = servers[1]
    upload(api, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n003,-6.2,106.8\n")
    batch = upload(api, "pdpj", "IDPEL,LAT,LON\n" + "001,-6.2,106.8\n" * 2400 + "002,-6.2,106.8\n")
    target = upload(api, "idpel_tidak_ketemu", "IDPEL,NAMA,LAT,LON\n999,Target,-6.2,106.8\n")
    page.goto(f"/pdpj?batch_id={batch}")
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Bertahap")
    with page.expect_response(lambda response: response.url.endswith("/advance") and response.status == 200):
        page.get_by_role("button", name="Periksa IDPEL ke master", exact=True).click()
    page.get_by_role("button", name="Hentikan sementara", exact=True).click()
    progress = page.get_by_role("region", name="Progres pemeriksaan PDPJ")
    expect(progress.get_by_role("status")).to_have_text("Proses dijeda · siap dilanjutkan")
    review_id = int(page.url.split("review_id=")[1])
    path = f"{api}/pdpj/reviews/{review_id}"
    before = httpx.get(path).json()
    finish = page.get_by_role("button", name="Selesaikan validasi data tersimpan", exact=True)
    expect(finish).to_be_enabled()
    finish.click()
    dialog = page.get_by_role("dialog", name="Data tersimpan selesai divalidasi", exact=True)
    expect(dialog).to_be_visible()
    stored = httpx.get(path).json()
    snapshot = stored["publications"][0]
    assert stored["processing"] == before["processing"]
    assert snapshot["publication"]["row_count"] < 2401
    dialog.get_by_role("link", name="Buka Data Koreksi", exact=True).click()
    expect(page.get_by_label("PDPJ selesai divalidasi", exact=True)).to_have_value(str(snapshot["id"]))
    launch(page)
    process_id = int(page.url.split("process_id=")[1])
    page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
    expect(detail.get_by_role("heading", name="Kandidat tersimpan (1)", exact=True)).to_be_visible()
    expect(detail.get_by_role("article")).to_contain_text("003")

    page.goto(f"/pdpj?batch_id={batch}&review_id={review_id}")
    expect(page.get_by_role("region", name="Versi PDPJ untuk koreksi")).to_contain_text("Versi 1")
    page.get_by_role("button", name="Lanjutkan pemeriksaan", exact=True).click()
    expect(progress.get_by_role("progressbar")).to_have_attribute("value", "100", timeout=30000)
    assert httpx.get(path).json()["processing"]["processed_rows"] == 2401
    assert httpx.get(f"{api}/pdpj/reviews/{snapshot['id']}").json()["summary"]["total_rows"] == snapshot["publication"]["row_count"]
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Bertahap")
    page.get_by_role("button", name="Selesaikan validasi PDPJ", exact=True).click()
    expect(page.get_by_role("dialog", name="PDPJ selesai divalidasi", exact=True)).to_be_visible()
    page.goto(f"/koreksi/idpel-tidak-ketemu?batch_id={target}&process_id={process_id}")
    expect(page.get_by_role("region", name="Pembaruan versi PDPJ")).to_be_visible()
    expect(page.get_by_label("PDPJ selesai divalidasi", exact=True)).to_have_value(str(snapshot["id"]))
    saved_check = httpx.get(f"{api}/corrections/idpel_tidak_ketemu/checks/{process_id}").json()
    assert saved_check["pdpj_review_id"] == snapshot["id"]
    assert saved_check["pdpj_update"]["review_id"] == review_id
