"""Historical coordinates remain traceable in correction details and the map."""

import httpx
from playwright.sync_api import Page, expect
from test_corrections_browser import upload


def test_all_observations_source_and_coordinate_warning_survive_refresh(
    page: Page, servers: tuple[str, str],
) -> None:
    api = servers[1]
    upload(api, "pascabayar", "IDPEL,LAT,LON,TGLBACA\n002,-6.2002,106.8,2025-01-01\n")
    upload(api, "pascabayar", "IDPEL,LAT,LON,TGLBACA\n002,-6.21,106.8,2026-01-01\n")
    upload(api, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2001,106.8\n")
    pdpj = upload(api, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    review = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": pdpj}).json()
    response = httpx.post(f"{api}/pdpj/reviews/{review['id']}/complete", json={"revision": review["revision"], "actor": "Uji Browser"})
    response.raise_for_status()
    batch = upload(api, "idpel_kosong", "NAMA,LAT,LON\nTarget,-6.2,106.8\n")
    page.goto(f"/koreksi/idpel-kosong?batch_id={batch}")
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Uji Browser")
    page.get_by_label("Radius pemeriksaan (meter)", exact=True).fill("50")
    page.get_by_role("button", name="Jalankan pemeriksaan", exact=True).click()
    dialog = page.get_by_role("dialog", name="Pemeriksaan koreksi selesai", exact=True)
    expect(dialog).to_be_visible(timeout=30000)
    dialog.get_by_role("button", name="Lihat hasil pemeriksaan", exact=True).click()
    expect(page.get_by_text("Pemeriksaan ini mencari seluruh observasi PR/PC dan DIL.", exact=False)).to_be_visible()
    for _ in range(2):
        page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
        detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
        expect(detail.get_by_role("article")).to_have_count(1)
        expect(detail).to_contain_text("Sumber koordinat terpilih: dil.csv")
        expect(detail).to_contain_text("Lokasi IDPEL ini berbeda antar sumber")
        expect(detail).to_contain_text("-6.2001")
        page.reload()
    page.get_by_role("link", name="Buka Peta Koreksi", exact=True).click()
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    page.get_by_role("button", name="Tampilkan kandidat target", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates.get_by_role("article")).to_have_count(1)
    expect(candidates).to_contain_text("Sumber koordinat terpilih: dil.csv")
    expect(candidates).to_contain_text("Lokasi IDPEL ini berbeda antar sumber")
