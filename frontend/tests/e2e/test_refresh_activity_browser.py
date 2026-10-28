"""Refresh during real server work, observe it, and resume without duplicate requests."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic, sleep

import httpx
import pytest
from playwright.sync_api import Page, expect

from conftest import ROOT, servers as ordinary_servers
from test_corrections_browser import prepare, upload


@pytest.fixture(scope="module")
def activity_files(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("activity-gates")
    (folder / "controlled_activity.py").write_text('''
import os,time
from pathlib import Path
from app.main import app
from app.modules.pdpj import service as pdpj
from app.modules.pdpj import router as pdpj_router
from app.modules.corrections import progress as correction
folder=Path(os.environ["E2E_ACTIVITY_CONTROL"])
def gate(original,name):
    def work(*args,**kwargs):
        block=folder/"block"
        if block.exists() and block.read_text()==name:
            (folder/"entered").write_text(name)
            deadline=time.monotonic()+40
            while not (folder/"release").exists():
                if time.monotonic()>deadline: raise RuntimeError("Activity test was not released")
                time.sleep(.02)
        return original(*args,**kwargs)
    return work
pdpj.match_processing_chunk=gate(pdpj.match_processing_chunk,"pdpj_matching")
pdpj.validate_processing_rows=gate(pdpj.validate_processing_rows,"pdpj_validating")
pdpj_router.complete_validation=gate(pdpj_router.complete_validation,"pdpj_publishing")
correction.advance_preparation=gate(correction.advance_preparation,"correction_preparing")
correction.run_correction_matching=gate(correction.run_correction_matching,"correction_matching")
''', encoding="utf-8")
    return folder


@pytest.fixture(scope="module")
def servers(tmp_path_factory: pytest.TempPathFactory, activity_files: Path):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("E2E_ASGI_APP", "controlled_activity:app")
        patch.setenv("E2E_ACTIVITY_CONTROL", str(activity_files))
        patch.setenv("PYTHONPATH", os.pathsep.join((str(activity_files), str(ROOT / "backend"))))
        yield from ordinary_servers.__wrapped__(tmp_path_factory)


@pytest.mark.parametrize("stage", ["pdpj_matching", "pdpj_validating", "pdpj_publishing", "correction_preparing", "correction_matching"])
def test_refresh_observes_actual_server_activity_and_then_offers_resume(
    page: Page, servers: tuple[str, str], activity_files: Path, stage: str
) -> None:
    for name in ("block", "entered", "release"):
        (activity_files / name).unlink(missing_ok=True)
    api = servers[1]
    reference = prepare(api, candidates=2)
    if stage.startswith("pdpj"):
        batch = upload(api, "pdpj", "IDPEL,LAT,LON\n" + "002,-6.2,106.8\n" * 3)
        started = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": batch, "incremental": True})
        started.raise_for_status()
        checkpoint = started.json()
        base = f"{api}/pdpj/reviews/{checkpoint['id']}"
        url = f"/pdpj?batch_id={batch}&review_id={checkpoint['id']}"
        region = "Progres pemeriksaan PDPJ"
        resume_label = "Lanjutkan pemeriksaan"
        if stage != "pdpj_matching":
            while checkpoint["processing"]["stage"] == "matching" or (stage == "pdpj_publishing" and checkpoint["processing"]["state"] != "ready"):
                response = httpx.post(base + "/advance", json={"revision": checkpoint["revision"], "chunk_size": 1})
                response.raise_for_status()
                checkpoint = response.json()
        identity = {}
        payload = {"revision": checkpoint["revision"], "actor": "Petugas Uji"} if stage == "pdpj_publishing" else {"revision": checkpoint["revision"], "chunk_size": 1}
    else:
        batch = upload(api, "idpel_kosong", "NAMA,LAT,LON\n" + "Target,-6.2,106.8\n" * 3)
        started = httpx.post(f"{api}/corrections/idpel_kosong/checks", json={"batch_id": batch, "pdpj_review_id": reference, "radius_meters": 10, "actor": "Petugas", "request_key": "refresh_activity_test", "incremental": True})
        started.raise_for_status()
        check = started.json()
        base = f"{api}/corrections/idpel_kosong/checks/{check['process_id']}"
        url = f"/koreksi/idpel-kosong?batch_id={batch}&process_id={check['process_id']}"
        region = "Progres pemeriksaan koreksi"
        resume_label = "Lanjutkan pemeriksaan koreksi"
        checkpoint = check["latest_run"]
        identity = {"run_id": checkpoint["id"]}
        if stage == "correction_matching":
            response = httpx.post(base + "/advance", json={**identity, "revision": checkpoint["processing"]["revision"]})
            response.raise_for_status()
            checkpoint = response.json()
        payload = {**identity, "revision": checkpoint["processing"]["revision"], "chunk_size": 1}
    (activity_files / "block").write_text(stage)
    with ThreadPoolExecutor(max_workers=1) as executor:
        request = executor.submit(httpx.post, base + ("/complete" if stage == "pdpj_publishing" else "/advance"), json=payload, timeout=35)
        try:
            deadline = monotonic() + 10
            while not (activity_files / "entered").exists() and monotonic() < deadline:
                sleep(.02)
            assert (activity_files / "entered").exists()
            page.goto(url)
            progress = page.get_by_role("region", name=region, exact=True)
            expect(progress).to_have_attribute("aria-busy", "true")
            page.reload()
            expect(progress).to_have_attribute("aria-busy", "true")
            expect(progress.locator(".animate-spin").first).to_be_visible()
            expect(progress.get_by_role("button", name=resume_label, exact=True)).to_have_count(0)
            if stage == "pdpj_publishing":
                page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Refresh")
                expect(page.get_by_role("button", name="Selesaikan validasi PDPJ", exact=True)).to_be_disabled()
            else:
                duplicate = httpx.post(base + "/advance", json=payload)
                assert duplicate.status_code == 409
        finally:
            (activity_files / "release").write_text("release")
        response = request.result(timeout=15)
        response.raise_for_status()
    expect(progress).to_have_attribute("aria-busy", "false", timeout=15000)
    assert not httpx.get(base + "/progress").json()["activity"]["active"]
    if stage != "pdpj_publishing":
        expect(progress.get_by_role("status")).to_have_text("Menunggu dilanjutkan dari hasil tersimpan")
        expect(progress.get_by_role("button", name=resume_label, exact=True)).to_be_enabled()
        progress.get_by_role("button", name=resume_label, exact=True).click()
        expect(progress.get_by_role("progressbar")).to_have_attribute("value", "100", timeout=20000)
