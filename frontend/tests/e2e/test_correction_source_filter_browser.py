"""Category source options and table filters against isolated API services."""
import httpx
import pytest
from playwright.sync_api import Page, expect
from test_manual_corrections_browser import fill_point


def put(api, kind, filename, content):
    response = httpx.post(api + "/upload/", data={"dataset_type": kind}, files={"file": (filename, content.encode(), "text/csv")})
    response.raise_for_status()
    batch = response.json()["id"]
    response = httpx.post(api + "/upload/confirm-mapping", json={"batch_id": batch, "column_mapping": {}})
    response.raise_for_status()
    return batch


@pytest.mark.parametrize("kind,slug,label,idpel,other", [
    ("idpel_kosong", "idpel-kosong", "IDPEL Kosong", "", "idpel_tidak_ketemu"),
    ("idpel_tidak_ketemu", "idpel-tidak-ketemu", "IDPEL Tidak Ketemu", "777", "idpel_kosong"),
])
def test_table_source_selection(page: Page, servers, kind, slug, label, idpel, other):
    api = servers[1]
    document = put(api, kind, "dokumen-target.csv", "IDPEL,NAMA,LAT,LON\n777,Alpha,-6.2,106.8\n888,Beta,-6.2,106.8\n")
    put(api, other, "kategori-lain.csv", "IDPEL,NAMA,LAT,LON\n999,Lain,-6.2,106.8\n")
    put(api, "pdpj", "acuan.csv", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    # Save through the real manual form, rather than manufacturing provenance.
    fill_point(page, idpel)
    page.get_by_role("button", name="Simpan & Buka Data Koreksi", exact=True).click()
    page.wait_for_url(f"**/koreksi/{slug}?*")
    page.goto(f"/koreksi/{slug}")
    source = page.get_by_label(f"Filter sumber {label}", exact=True)
    expect(source.locator("option")).to_have_count(3)
    expect(source.locator("option")).to_contain_text(["Semua Sumber", "Input Manual", "dokumen-target.csv"])
    table = page.get_by_role("table")
    expect(table.locator("tbody tr")).to_have_count(3)
    source.select_option(f"batch:{document}")
    expect(table.locator("tbody tr")).to_have_count(2)
    page.get_by_label(f"Cari {label}", exact=True).fill("Alpha")
    expect(table.locator("tbody tr")).to_have_count(1)
    expect(table).to_contain_text("Alpha")
    page.get_by_label(f"Cari {label}", exact=True).fill("")
    source.select_option("manual")
    expect(table.locator("tbody tr")).to_have_count(1)
    expect(table).not_to_contain_text("Alpha")
    expect(table).not_to_contain_text("Beta")
    page.get_by_label(f"Filter status {label}", exact=True).select_option("candidates_found")
    expect(table).to_contain_text("Tidak ada data sesuai pencarian atau filter.")
    page.get_by_label(f"Filter status {label}", exact=True).select_option("all")
    source.select_option("all")
    expect(table.locator("tbody tr")).to_have_count(3)
