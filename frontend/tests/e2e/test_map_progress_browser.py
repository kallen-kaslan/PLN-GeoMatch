"""Radius expansion exposes real checkpoints and recovers scope during server work."""

import re
from pathlib import Path

import httpx
import pytest
import test_refresh_activity_browser as refresh_controls
from playwright.sync_api import Page, Route, expect
from test_correction_map_browser import setup_map
from test_processing_progress_browser import captured

activity_files = refresh_controls.activity_files
servers = refresh_controls.servers


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_radius_expansion_progress_refresh_pause_resume_and_retained_choices(
    page: Page, servers: tuple[str, str], activity_files: Path, kind: str
) -> None:
    for name in ("block", "entered", "release"):
        (activity_files / name).unlink(missing_ok=True)
    _, process = setup_map(page, servers[1], kind=kind, count=205)
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    page.get_by_label("Petugas peta", exact=True).fill("Petugas Perluasan")
    page.get_by_role("button", name="Tampilkan kandidat target", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("12 kandidat tersimpan")
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    detail = page.get_by_role("region", name="Detail target terpilih", exact=True)
    expect(detail).to_contain_text("Pilihan aktif: 002")
    page.get_by_label("Radius perluasan (meter)", exact=True).fill("150")
    (activity_files / "block").write_text("correction_matching")
    page.get_by_role(
        "button", name="Perluas pemeriksaan dan tampilkan kandidat", exact=True
    ).click()
    progress = page.get_by_role("region", name="Progres pemeriksaan koreksi")
    base = f"{servers[1]}/corrections/{kind}/checks/{process}"
    try:
        expect(progress).to_have_attribute("aria-busy", "true")
        expect(progress).to_contain_text("Radius 150 m · Seluruh berkas")
        expect(progress.get_by_role("heading")).to_have_text(
            "Memeriksa benturan dan menyimpan kandidat"
        )
        expect(progress.get_by_label("Estimasi waktu tahap koreksi")).to_contain_text(
            "belum cukup data"
        )
        expect(page.get_by_label("Radius peta (meter)", exact=True)).to_be_disabled()
        expect(detail).to_have_count(0)
        latest_summary = page.get_by_role(
            "region", name="Ringkasan radius peta", exact=True
        )
        expect(latest_summary).to_contain_text("Radius 150 m · Versi 2")
        expect(latest_summary).to_contain_text(
            "Hasil sementara: 0 dari 206 baris tersimpan."
        )
        expect(
            page.get_by_role("region", name="Pembaruan radius peta", exact=True)
        ).to_have_count(0)
        expect(
            progress.get_by_text(re.compile(r"0 menit [1-9]\d* detik"))
        ).to_be_visible(timeout=10000)
        assert (activity_files / "entered").exists()
        restoring: list[Route] = []
        status_url = f"**/corrections/{kind}/checks/{process}?*"
        page.route(status_url, lambda route: restoring.append(route))
        page.reload()
        status = captured(page, restoring)
        expect(
            page.get_by_text("Memulihkan pemeriksaan dan status proses dari server…")
        ).to_be_visible()
        expect(page.get_by_label("Radius peta (meter)", exact=True)).to_be_disabled()
        status.continue_()
        page.unroute(status_url)
        expect(progress).to_have_attribute("aria-busy", "true")
        expect(progress.locator(".animate-spin").first).to_be_visible()
        expect(progress).to_contain_text("Radius 150 m · Seluruh berkas")
        expect(page.get_by_label("Radius peta (meter)", exact=True)).to_have_value(
            "150"
        )
        expect(page.get_by_label("Radius peta (meter)", exact=True)).to_be_disabled()
        expect(page.get_by_label("Petugas peta", exact=True)).to_have_value(
            "Petugas Perluasan"
        )
        expect(detail).to_have_count(0)
        expect(latest_summary).to_contain_text("Radius 150 m · Versi 2")
        expect(
            progress.get_by_role("button", name="Lanjutkan pemeriksaan koreksi")
        ).to_have_count(0)
        assert len(httpx.get(base).json()["runs"]) == 2
        # A finished radius remains readable while the next radius is working.
        versions = page.get_by_label("Versi radius pemeriksaan", exact=True)
        versions.select_option("1")
        radius = page.get_by_label("Radius peta (meter)", exact=True)
        expect(radius).to_be_enabled()
        radius.fill("1")
        expect(latest_summary).to_contain_text("Radius 1 m · Versi 1")
        refresh = page.get_by_role(
            "button", name="Perbarui ringkasan radius", exact=True
        )
        expect(refresh).to_be_enabled()
        refresh.click()
        page.get_by_role("button", name="Tampilkan kandidat target", exact=True).click()
        expect(candidates).to_contain_text("12 kandidat tersimpan")
        assert len(httpx.get(base).json()["runs"]) == 2
        versions.select_option("2")
        expect(radius).to_have_value("150")
        expect(radius).to_be_disabled()
    finally:
        (activity_files / "release").write_text("release")
    expect(progress).to_have_attribute("aria-busy", "false", timeout=15000)
    expect(progress.get_by_text("100 / 206 baris", exact=True)).to_be_visible()
    update = page.get_by_role("region", name="Ringkasan radius peta", exact=True)
    expect(update).to_contain_text("Hasil sementara: 100 dari 206 baris tersimpan.")
    expect(
        update.get_by_text("Belum diperiksa", exact=True).locator("..").locator("dd")
    ).to_have_text("106")
    expect(
        update.get_by_text("Baris tanpa kandidat", exact=True)
        .locator("..")
        .locator("dd")
    ).to_have_text("0")
    expect(detail).to_contain_text("Pilihan aktif: 002")
    page.get_by_role("button", name="Tampilkan kandidat target", exact=True).click()
    expect(progress.get_by_label("Estimasi waktu tahap koreksi")).to_contain_text(
        "Perkiraan waktu kerja tersisa"
    )
    held: list[Route] = []
    page.route(
        f"**/corrections/{kind}/checks/{process}/advance",
        lambda route: held.append(route),
    )
    progress.get_by_role("button", name="Lanjutkan pemeriksaan koreksi").click()
    step = captured(page, held)
    progress.get_by_role("button", name="Hentikan sementara koreksi").click()
    expect(
        progress.get_by_role("button", name="Menyimpan bagian aktif…")
    ).to_be_disabled()
    step.continue_()
    expect(progress).to_contain_text("Proses dijeda · siap dilanjutkan", timeout=10000)
    expect(progress.get_by_text("200 / 206 baris", exact=True)).to_be_visible()
    page.unroute(f"**/corrections/{kind}/checks/{process}/advance")
    page.reload()
    expect(progress).to_contain_text("Proses dijeda · siap dilanjutkan")
    expect(progress.get_by_text("200 / 206 baris", exact=True)).to_be_visible()
    expect(page.get_by_label("Radius peta (meter)", exact=True)).to_have_value("150")
    expect(detail).to_contain_text("Pilihan aktif: 002")
    progress.get_by_role("button", name="Lanjutkan pemeriksaan koreksi").click()
    expect(candidates).to_contain_text("13 kandidat tersimpan", timeout=30000)
    expect(progress).to_have_count(0)
    expect(page.get_by_role("region", name="Ringkasan radius peta")).to_contain_text(
        "Radius 150 m · Versi 2"
    )
    expect(detail).to_contain_text("Pilihan aktif: 002")
    expect(detail).to_contain_text("Versi pencarian 1")
    check = httpx.get(base).json()
    assert len(check["runs"]) == 2 and check["current_generation"] == 2
    assert check["latest_run"]["processing"]["processed_rows"] == 206
    page.reload()
    expect(progress).to_have_count(0)
    expect(candidates).to_contain_text("13 kandidat tersimpan")
    expect(detail).to_contain_text("Pilihan aktif: 002")
