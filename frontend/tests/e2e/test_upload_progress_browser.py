"""Progress counters, ETA, disconnect feedback, and completion in the import UI."""

import time

import httpx
import pytest
from playwright.sync_api import Page, Route, expect


def test_master_import_displays_measured_progress_and_waits_for_commit(
    page: Page, servers: tuple[str, str]
) -> None:
    pending = []
    processed = 1
    disconnected = False

    def hold_validation(route: Route) -> None:
        pending.append(route)

    def progress_snapshot(route: Route) -> None:
        if not pending:
            route.continue_()
            return
        if disconnected:
            route.fulfill(status=503, json={"detail": "Pembaruan sementara terputus"})
            return
        now = time.time()
        route.fulfill(json={
            "id": route.request.url.rsplit("/", 1)[-1],
            "phase": "validating", "status": "running", "processed": processed,
            "total": 4, "unit": "rows", "started_at": now - 8,
            "phase_started_at": now - 5, "updated_at": now,
        })

    page.route("**/api/upload/confirm-mapping", hold_validation)
    page.route("**/api/upload/progress/*", progress_snapshot)
    page.goto("/master/dil")
    page.get_by_role("button", name="Unggah berkas", exact=True).click()
    page.locator("input[type=file]").set_input_files({
        "name": "progres.csv", "mimeType": "text/csv",
        "buffer": b"IDPEL,NAMA,LAT,LON\n001,Satu,-6.2,106.8\n002,Dua,-6.2,106.8\n003,Tiga,-6.2,106.8\n004,Empat,-6.2,106.8\n",
    })
    save = page.get_by_role("button", name="Simpan dan validasi master", exact=True)
    expect(save).to_be_enabled()
    panel = page.get_by_role("region", name="Progres impor data", exact=True)
    expect(panel).to_contain_text("Pratinjau siap")
    save.click()
    bar = panel.get_by_role("progressbar", name="Progres tahap impor", exact=True)
    expect(bar).to_have_attribute("value", "1")
    expect(bar).to_have_attribute("max", "4")
    expect(panel).to_contain_text("25% tahap ini")
    expect(panel).to_contain_text("1 baris dari 4 baris")
    expect(panel).to_contain_text("Sekitar")
    expect(panel.locator("svg.animate-spin").first).to_be_visible()
    assert httpx.get(f"{servers[1]}/master/dil/summary").json()["total_rows"] == 0
    processed = 3
    expect(bar).to_have_attribute("value", "3")
    expect(panel).to_contain_text("75% tahap ini")
    disconnected = True
    expect(panel).to_contain_text("Pembaruan progres belum tersambung", timeout=10000)
    expect(bar).to_have_attribute("value", "3")
    expect(page.get_by_role("button", name="Menyimpan dan memvalidasi", exact=False)).to_be_disabled()
    expect(page.get_by_text("progres.csv berhasil disimpan.", exact=True)).to_have_count(0)
    pending.pop().continue_()
    expect(page.get_by_text("progres.csv berhasil disimpan.", exact=True)).to_be_visible()
    assert httpx.get(f"{servers[1]}/master/dil/summary").json()["total_rows"] == 4


@pytest.mark.parametrize("phase", ["import", "validation"])
def test_pause_and_resume_master_import_waits_for_server_acknowledgement(
    page: Page, servers: tuple[str, str], phase: str
) -> None:
    pending = []
    failed_pause = failed_resume = False
    pattern = "**/api/upload/files/*/import-sheet" if phase == "import" else "**/api/upload/confirm-mapping"
    page.route(pattern, lambda route: pending.append(route))

    def control(route: Route) -> None:
        nonlocal failed_pause, failed_resume
        if phase == "validation" and route.request.url.endswith("/pause") and not failed_pause:
            failed_pause = True
            route.fulfill(status=503, json={"detail": "Perintah jeda belum tersambung"})
        elif phase == "validation" and route.request.url.endswith("/resume") and not failed_resume:
            failed_resume = True
            route.fulfill(status=503, json={"detail": "Perintah lanjutkan belum tersambung"})
        else:
            route.continue_()

    page.route("**/api/upload/progress/*/pause", control)
    page.route("**/api/upload/progress/*/resume", control)
    page.goto("/master/dil")
    page.get_by_role("button", name="Unggah berkas", exact=True).click()
    page.locator("input[type=file]").set_input_files({
        "name": "pause.csv", "mimeType": "text/csv",
        "buffer": b"IDPEL,NAMA,LAT,LON\n001,Satu,-6.2,106.8\n002,Dua,-6.2,106.8\n003,Tiga,-6.2,106.8\n",
    })
    save = page.get_by_role("button", name="Simpan dan validasi master", exact=True)
    expect(save).to_be_enabled()
    with page.expect_request(lambda request: request.method == "POST" and (request.url.endswith("/import-sheet") if phase == "import" else request.url.endswith("/confirm-mapping"))):
        save.click()
    panel = page.get_by_role("region", name="Progres impor data", exact=True)
    pause = panel.get_by_role("button", name="Pause", exact=True)
    pause.click()
    if phase == "validation":
        expect(panel.get_by_role("alert")).to_have_text("Perintah jeda belum tersambung")
        expect(panel.get_by_role("button", name="Lanjutkan", exact=True)).to_have_count(0)
        pause.click()
    expect(panel).to_contain_text("Jeda diminta")
    assert len(pending) == 1
    token = pending[0].request.header_value("x-upload-progress")
    assert token is not None
    pending.pop().continue_()
    expect(panel).to_contain_text("Proses dijeda", timeout=10000)
    expect(panel.locator("svg.animate-spin")).to_have_count(0)
    expect(panel).to_contain_text("Dijeda")
    snapshot = httpx.get(f"{servers[1]}/upload/progress/{token}").json()
    assert snapshot["status"] == "paused"
    assert snapshot["pause_requested"]
    assert httpx.get(f"{servers[1]}/master/dil/summary").json()["total_rows"] == 0
    expect(page.get_by_text("pause.csv berhasil disimpan.", exact=True)).to_have_count(0)
    resume = panel.get_by_role("button", name="Lanjutkan", exact=True)
    resume.click()
    if phase == "validation":
        expect(panel.get_by_role("alert")).to_have_text("Perintah lanjutkan belum tersambung")
        expect(panel).to_contain_text("Proses dijeda")
        assert httpx.get(f"{servers[1]}/upload/progress/{token}").json()["status"] == "paused"
        resume.click()
    expect(page.get_by_text("pause.csv berhasil disimpan.", exact=True)).to_be_visible(timeout=10000)
    records = httpx.get(f"{servers[1]}/master/dil/records").json()
    assert records["total"] == 3
    assert [row["fields"]["idpel"] for row in records["items"]] == ["001", "002", "003"]


def test_preview_worker_can_pause_and_resume_without_losing_preview_rows(page: Page) -> None:
    page.goto("/master/dil")
    result = page.evaluate("""async () => {
      const { readMasterPreview } = await import('/src/lib/master-preview.ts');
      let acknowledge;
      const paused = new Promise(resolve => { acknowledge = resolve; });
      const updates = [];
      const task = readMasterPreview(new File(['IDPEL,NAMA\\n001,Satu\\n002,Dua'], 'preview.csv'), 'dil',
        (processed) => updates.push(processed), (value) => { if (value) acknowledge(); });
      task.pause();
      const first = await Promise.race([paused.then(() => 'paused'), task.result.then(() => 'completed')]);
      if (first !== 'paused') throw new Error('Preview finished without acknowledging Pause');
      const before = updates.length;
      await new Promise(resolve => setTimeout(resolve, 100));
      if (updates.length !== before) throw new Error('Preview progressed while paused');
      task.resume();
      return (await task.result).preview;
    }""")
    assert result["headers"] == ["IDPEL", "NAMA"]
    assert [row["IDPEL"] for row in result["rows"]] == ["001", "002"]
