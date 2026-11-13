"""The dashboard represents stored work and keeps PLN navigation usable."""

import httpx
import pytest
from playwright.sync_api import expect
from test_corrections_browser import prepare, upload


def test_dashboard_empty_state_and_pln_brand(page, servers):
    page.goto("/")
    expect(page.get_by_role("heading", name="Dashboard", exact=True)).to_be_visible()
    expect(page.get_by_text("Tidak ada pekerjaan yang menunggu tindakan.", exact=True)).to_be_visible()
    sidebar = page.get_by_role("complementary", name="Navigasi Utama Aplikasi", exact=True)
    logo = sidebar.get_by_role("img", name="Logo PLN", exact=True)
    expect(logo).to_be_visible()
    assert logo.evaluate("image => image.complete && image.naturalWidth > 0")
    expect(page.get_by_role("link", name="Buka Data PDPJ", exact=True)).to_be_visible()
    expect(page.get_by_role("progressbar", name="Pemeriksaan selesai ditinjau")).to_have_attribute("value", "0")


@pytest.mark.parametrize("mobile", [False, True])
def test_dashboard_uses_real_work_status_and_continues_selected_process(page, servers, mobile):
    api = servers[1]
    review = prepare(api, candidates=2)
    saved = []
    for index, kind in enumerate(("idpel_kosong", "idpel_tidak_ketemu")):
        batch = upload(api, kind, "IDPEL,NAMA,LAT,LON\n" + f"{'' if index == 0 else '999'},Target dashboard,-6.2,106.8\n")
        checked = httpx.post(f"{api}/corrections/{kind}/checks", json={"batch_id": batch, "pdpj_review_id": review, "radius_meters": 10, "actor": "ignored", "request_key": f"dashboard_check_{index}", "incremental": True})
        checked.raise_for_status()
        check = checked.json()
        run = check["latest_run"]
        base = f"{api}/corrections/{kind}/checks/{check['process_id']}"
        if index == 0:
            for _ in range(15):
                if run["status"] == "completed":
                    break
                response = httpx.post(base + "/advance", json={"run_id": run["id"], "revision": run["processing"]["revision"], "chunk_size": 100})
                response.raise_for_status()
                run = response.json()
            assert run["status"] == "completed"
        else:
            httpx.post(base + "/pause", json={"run_id": run["id"]}).raise_for_status()
        saved.append(check)
    page.set_viewport_size({"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900})
    page.goto("/")
    metrics = page.get_by_role("region", name="Ringkasan aktivitas", exact=True)
    expect(metrics.get_by_text("Pemeriksaan tersimpan", exact=True).locator("..").get_by_text("2", exact=True)).to_be_visible()
    overview = page.get_by_role("complementary", name="Ikhtisar ruang kerja", exact=True)
    expect(overview.get_by_text("Siap ditinjau", exact=True).locator("..").locator("..").get_by_text("1", exact=True)).to_be_visible()
    expect(overview.get_by_text("Dijeda", exact=True).locator("..").locator("..").get_by_text("1", exact=True)).to_be_visible()
    queue = page.get_by_role("region", name="Pekerjaan rekonsiliasi", exact=True)
    expect(queue.get_by_role("row")).to_have_count(3)
    resume = page.get_by_role("link", name="Lanjutkan pekerjaan", exact=True)
    expect(resume).to_have_attribute("href", f"/koreksi/idpel-tidak-ketemu?batch_id={saved[1]['batch_id']}&process_id={saved[1]['process_id']}")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if mobile:
        page.get_by_role("button", name="Buka menu navigasi", exact=True).click()
        menu = page.get_by_role("dialog", name="Menu Navigasi Mobile", exact=True)
        expect(menu.get_by_role("img", name="Logo PLN", exact=True)).to_be_visible()
        page.keyboard.press("Escape")
        expect(menu).not_to_be_visible()
    resume.click()
    expect(page.get_by_label("Berkas koreksi", exact=True)).to_have_value(str(saved[1]["batch_id"]))
