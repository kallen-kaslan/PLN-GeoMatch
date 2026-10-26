"""Exercise PDPJ import, recommendation selection, manual edits, and completion in a browser."""

from pathlib import Path

import httpx
from playwright.sync_api import Page, Route, expect


def test_pdpj_mapping_storage_error_can_retry_without_uploading_again(
    page: Page, servers: tuple[str, str]
) -> None:
    calls = 0
    message = (
        "Database gagal menulis ke disk. Periksa akses folder database dan ruang disk."
    )

    def confirm(route: Route) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            route.fulfill(status=503, json={"detail": message})
        else:
            route.continue_()

    page.route("**/api/upload/confirm-mapping", confirm)
    page.goto("/pdpj")
    page.get_by_role("button", name="Unggah PDPJ", exact=True).click()
    page.locator("input[type=file]").set_input_files(
        {
            "name": "retry.csv",
            "mimeType": "text/csv",
            "buffer": b"IDPEL,NAMA\n001,Sumber\n",
        }
    )
    save = page.get_by_role("button", name="Simpan dan validasi PDPJ", exact=True)
    save.click()
    expect(page.get_by_role("alert")).to_have_text(message)
    assert len(httpx.get(f"{servers[1]}/pdpj/batches").json()) == 1
    save.click()
    expect(page.get_by_role("status")).to_contain_text("retry.csv tersimpan")
    batches = httpx.get(f"{servers[1]}/pdpj/batches").json()
    assert len(batches) == 1 and batches[0]["status"] == "completed"
    assert calls == 2


def upload_source(api_url: str, kind: str, content: str, name: str) -> int:
    response = httpx.post(
        f"{api_url}/upload/",
        data={"dataset_type": kind},
        files={"file": (name, content.encode(), "text/csv")},
    )
    response.raise_for_status()
    batch_id = response.json()["id"]
    mapping = {"lat": "LAT", "lon": "LON"} if kind == "target" else {"idpel": "IDPEL"}
    checked = httpx.post(
        f"{api_url}/upload/confirm-mapping",
        json={"batch_id": batch_id, "column_mapping": mapping},
    )
    checked.raise_for_status()
    return batch_id


def test_bulk_exceptions_enable_correction_map_and_preserve_reserved_identities(
    page: Page, servers: tuple[str, str]
) -> None:
    api = servers[1]
    upload_source(
        api,
        "dil",
        "IDPEL,NAMA,LAT,LON\n001,PDPJ lengkap,-6.2,106.8\n002,PDPJ belum lengkap,-6.2,106.8\n003,Kandidat tersisa,-6.2,106.8\n",
        "master-bulk.csv",
    )
    batch = upload_source(
        api,
        "pdpj",
        "IDPEL,NAMA,LAT,LON\n001,Lengkap,-6.2,106.8\n002,Belum lengkap,,\n009,Tidak ditemukan,-6.2,106.8\n",
        "pdpj-bulk.csv",
    )
    created = httpx.post(f"{api}/pdpj/reviews", json={"batch_id": batch})
    created.raise_for_status()
    review = created.json()["id"]
    page.goto(f"/pdpj?batch_id={batch}&review_id={review}")
    expect(
        page.get_by_role("button", name="Selesaikan validasi PDPJ", exact=True)
    ).to_be_disabled()
    page.get_by_role(
        "button", name="Lanjutkan dengan pengecualian massal", exact=True
    ).click()
    dialog = page.get_by_role(
        "dialog", name="Lanjutkan dengan pengecualian massal", exact=True
    )
    expect(dialog).to_contain_text("2 baris bermasalah")
    save = dialog.get_by_role(
        "button", name="Simpan pengecualian dan lanjutkan", exact=True
    )
    expect(save).to_be_disabled()
    dialog.get_by_label("Alasan pengecualian massal", exact=True).fill(
        "Referensi belum lengkap; lanjutkan koreksi dengan tindak lanjut tercatat"
    )
    dialog.get_by_role("checkbox").check()
    expect(save).to_be_disabled()
    dialog.get_by_label("Petugas penanggung jawab", exact=True).fill("Petugas Massal")
    expect(save).to_be_enabled()
    save.click()
    completed = page.get_by_role("dialog", name="PDPJ selesai divalidasi", exact=True)
    expect(completed).to_be_visible()
    completed.get_by_role("button", name="Lihat hasil validasi", exact=True).click()
    info = httpx.get(f"{api}/pdpj/reviews/{review}").json()
    assert info["status"] == "completed" and info["summary"]["exceptions"] == 2
    target = upload_source(
        api,
        "idpel_tidak_ketemu",
        "IDPEL,NAMA,LAT,LON\n999,Target peta,-6.2,106.8\n",
        "target-bulk.csv",
    )
    checked = httpx.post(
        f"{api}/corrections/idpel_tidak_ketemu/checks",
        json={
            "batch_id": target,
            "pdpj_review_id": review,
            "radius_meters": 10,
            "actor": "Petugas Massal",
            "request_key": "bulk_browser_map_check",
        },
        timeout=30,
    )
    checked.raise_for_status()
    process = checked.json()["process_id"]
    page.goto(
        f"/peta-koreksi?category=idpel_tidak_ketemu&batch_id={target}&process_id={process}"
    )
    point = page.get_by_role("button", name="Titik koreksi baris 2", exact=True)
    expect(point).to_be_visible(timeout=20000)
    point.click()
    page.get_by_role("button", name="Tampilkan kandidat target", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("1 kandidat tersimpan", timeout=20000)
    expect(candidates).to_contain_text("003")
    expect(candidates.get_by_role("article")).to_have_count(1)
    page.get_by_label("Petugas peta", exact=True).fill("Petugas Massal")
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    expect(
        page.get_by_role("region", name="Detail target terpilih", exact=True)
    ).to_contain_text("Pilihan aktif: 003", timeout=10000)


def test_pdpj_import_recommendations_manual_exception_completion_and_matching(
    page: Page,
    servers: tuple[str, str],
    tmp_path: Path,
) -> None:
    api_url = servers[1]
    upload_source(
        api_url,
        "prabayar",
        "IDPEL,NAMA,LAT,LON\n001,Referensi lama,,\n002,Kandidat tersisa,-6.2,106.8\n",
        "prabayar.csv",
    )
    upload_source(
        api_url,
        "dil",
        "IDPEL,NAMA,KOORDINAT_Y,KOORDINAT_X,NOMOR_GARDU\n001,Referensi DIL,-6.2,106.8,G1\n",
        "referensi-dil.csv",
    )
    page.goto("/pdpj")
    page.get_by_role("button", name="Unggah PDPJ", exact=True).click()
    page.locator("input[type=file]").set_input_files(
        {
            "name": "pdpj.csv",
            "mimeType": "text/csv",
            "buffer": b"IDPEL,NAMA,LAT,LON\n001,Nama Asli,,\n009,Tidak ketemu,-6.2,106.8\n",
        }
    )
    page.get_by_role("button", name="Simpan dan validasi PDPJ", exact=True).click()
    expect(page.get_by_role("status")).to_contain_text("pdpj.csv tersimpan")
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Browser")
    page.get_by_role("button", name="Periksa IDPEL ke master", exact=True).click()
    expect(
        page.get_by_role(
            "heading", name="Hasil pemeriksaan · Dalam pemeriksaan", exact=True
        )
    ).to_be_visible()
    finish = page.get_by_role("button", name="Selesaikan validasi PDPJ", exact=True)
    expect(finish).to_be_disabled()
    page.get_by_role("button", name="Detail PDPJ baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail pemeriksaan PDPJ", exact=True)
    expect(detail.get_by_text("Koordinat belum lengkap", exact=True)).to_be_visible()
    expect(
        detail.get_by_role(
            "heading", name="Rekomendasi dari seluruh sumber (2)", exact=True
        )
    ).to_be_visible()
    recommendation = detail.get_by_role("article").filter(
        has=page.get_by_role("heading", name="referensi-dil.csv", exact=True)
    )
    recommendation.get_by_role(
        "button", name="Terapkan kolom pilihan", exact=True
    ).click()
    expect(detail.get_by_text("Koordinat lengkap", exact=True)).to_be_visible()
    detail.get_by_text("Isi atau perbaiki data secara manual", exact=True).click()
    detail.get_by_label("Manual Nama pelanggan", exact=True).fill("Nama Manual")
    detail.get_by_label("Alasan perubahan / pengecualian", exact=True).fill(
        "Konfirmasi nama pelanggan"
    )
    detail.get_by_role("button", name="Simpan perubahan manual", exact=True).click()
    expect(detail.get_by_role("cell", name="Nama Manual", exact=True)).to_be_visible()
    expect(
        detail.get_by_text("Pengisian manual · Petugas Browser", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Detail PDPJ baris 3", exact=True).click()
    expect(detail.get_by_text("IDPEL tidak ditemukan", exact=True)).to_be_visible()
    detail.get_by_label("Alasan perubahan / pengecualian", exact=True).fill(
        "Menunggu verifikasi lapangan; belum terdaftar pada master"
    )
    detail.get_by_role(
        "button", name="Simpan pengecualian kelengkapan", exact=True
    ).click()
    expect(finish).to_be_enabled()
    finish.click()
    dialog = page.get_by_role("dialog", name="PDPJ selesai divalidasi", exact=True)
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Lihat hasil validasi", exact=True).click()
    expect(
        page.get_by_role(
            "heading", name="Hasil pemeriksaan · Selesai divalidasi", exact=True
        )
    ).to_be_visible()
    page.screenshot(path=str(tmp_path / "pdpj-completed.png"), full_page=True)
    page.get_by_role("link", name="Lanjut ke Data Koreksi", exact=True).click()
    expect(page.get_by_role("heading", name="Data Koreksi", exact=True)).to_be_visible()
    expect(
        page.get_by_label("PDPJ selesai divalidasi", exact=True)
        .get_by_role("option")
        .filter(has_text="pdpj.csv")
    ).to_have_count(1)

    target = upload_source(
        api_url, "target", "NOMOR_METER,LAT,LON\nT1,-6.2,106.8\n", "koreksi.csv"
    )
    matched = httpx.post(
        f"{api_url}/upload/auto-pipeline", params={"batch_id": target}, timeout=20
    )
    matched.raise_for_status()
    assert matched.json()["status"] == "completed"
    candidates = httpx.get(
        f"{api_url}/process/{matched.json()['process_id']}/candidates"
    ).json()
    assert all(item["candidate_idpel"] != "001" for item in candidates["items"])
    assert any(item["candidate_idpel"] == "002" for item in candidates["items"])


def test_replacing_filled_recommendation_requires_explicit_overwrite(
    page: Page, servers: tuple[str, str]
) -> None:
    api_url = servers[1]
    upload_source(
        api_url, "dil", "IDPEL,NAMA,LAT,LON\n001,Nama Rujukan,-6.3,106.9\n", "dil.csv"
    )
    batch_id = upload_source(
        api_url, "pdpj", "IDPEL,NAMA,LAT,LON\n001,Nama Asli,-6.2,106.8\n", "pdpj.csv"
    )
    page.goto(f"/pdpj?batch_id={batch_id}")
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Browser")
    page.get_by_role("button", name="Periksa IDPEL ke master", exact=True).click()
    page.get_by_role("button", name="Detail PDPJ baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail pemeriksaan PDPJ", exact=True)
    card = detail.get_by_role("article")
    card.get_by_role(
        "checkbox", name="Pilih Nama pelanggan dari rekomendasi", exact=False
    ).check()
    apply = card.get_by_role("button", name="Terapkan kolom pilihan", exact=True)
    expect(apply).to_be_disabled()
    detail.get_by_label("Alasan perubahan / pengecualian", exact=True).fill(
        "Nama dikonfirmasi sesuai sumber DIL"
    )
    card.get_by_role(
        "checkbox", name="Saya menyetujui penggantian nilai terisi", exact=False
    ).check()
    apply.click()
    expect(detail.get_by_role("cell", name="Nama Rujukan", exact=True)).to_be_visible()
    expect(detail.get_by_role("cell", name="Nama Asli", exact=True)).to_be_visible()
    page.get_by_role("button", name="Selesaikan validasi PDPJ", exact=True).click()
    page.get_by_role("dialog").get_by_role(
        "button", name="Lihat hasil validasi", exact=True
    ).click()
    page.get_by_role("button", name="Periksa ulang PDPJ", exact=True).click()
    expect(
        page.get_by_role(
            "heading", name="Hasil pemeriksaan · Dalam pemeriksaan", exact=True
        )
    ).to_be_visible()
    page.get_by_role("button", name="Detail PDPJ baris 2", exact=True).click()
    expect(detail.get_by_role("cell", name="Nama Rujukan", exact=True)).to_be_visible()
    expect(
        page.get_by_label("Versi pemeriksaan", exact=True).locator("option")
    ).to_have_count(3)


def test_mobile_pending_pdpj_mapping_and_manual_coordinates(
    page: Page, servers: tuple[str, str]
) -> None:
    api_url = servers[1]
    upload_source(api_url, "dil", "IDPEL\n001\n", "dil-tanpa-koordinat.csv")
    response = httpx.post(
        f"{api_url}/upload/",
        data={"dataset_type": "pdpj"},
        files={"file": ("pending-pdpj.csv", b"CUSTOMER\n001\n", "text/csv")},
    )
    response.raise_for_status()
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/pdpj")
    page.get_by_role("button", name="Lanjutkan mapping PDPJ", exact=True).click()
    page.get_by_label("Kolom IDPEL", exact=True).select_option("CUSTOMER")
    page.get_by_role("button", name="Simpan dan validasi PDPJ", exact=True).click()
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Mobile")
    page.get_by_role("button", name="Periksa IDPEL ke master", exact=True).click()
    page.get_by_role("button", name="Detail PDPJ baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail pemeriksaan PDPJ", exact=True)
    detail.get_by_text("Isi atau perbaiki data secara manual", exact=True).click()
    detail.get_by_label("Manual Latitude (lintang)", exact=True).fill("-6.2")
    detail.get_by_label("Manual Longitude (bujur)", exact=True).fill("106.8")
    detail.get_by_role("button", name="Simpan perubahan manual", exact=True).click()
    expect(detail.get_by_text("Koordinat lengkap", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("button", name="Selesaikan validasi PDPJ", exact=True).click()
    expect(
        page.get_by_role("dialog", name="PDPJ selesai divalidasi", exact=True)
    ).to_be_visible()
