"""Categorized correction acceptance tests with stored candidates and real job completion."""

import httpx
from playwright.sync_api import Page, expect


def upload(api_url: str, kind: str, content: str) -> int:
    response = httpx.post(
        f"{api_url}/upload/",
        data={"dataset_type": kind},
        files={"file": (kind + ".csv", content.encode(), "text/csv")},
    )
    response.raise_for_status()
    batch_id = response.json()["id"]
    mapping = (
        {"idpel": "IDPEL"} if "IDPEL" in content.splitlines()[0].split(",") else {}
    )
    response = httpx.post(
        f"{api_url}/upload/confirm-mapping",
        json={"batch_id": batch_id, "column_mapping": mapping},
    )
    response.raise_for_status()
    return batch_id


def prepare(api_url: str, candidates: int = 7) -> int:
    master = "IDPEL,NAMA,LAT,LON,NOMOR_GARDU\n001,PDPJ,-6.2,106.8,G1\n"
    master += "".join(
        f"{number:03},Pelanggan {number},-6.2,106.8,G{number}\n"
        for number in range(2, candidates + 2)
    )
    master += "099,Agak jauh,-6.2005,106.8,G99\n"
    upload(api_url, "dil", master)
    pdpj = upload(
        api_url,
        "pdpj",
        "IDPEL,LAT,LON,NOMOR_METER,NOAGENDA,ID_TITIK\n001,-6.2,106.8,M1,A1,S1\n",
    )
    review = httpx.post(f"{api_url}/pdpj/reviews", json={"batch_id": pdpj}).json()
    finished = httpx.post(
        f"{api_url}/pdpj/reviews/{review['id']}/complete",
        json={"revision": review["revision"], "actor": "Petugas Browser"},
    )
    finished.raise_for_status()
    return review["id"]


def launch(page: Page) -> None:
    page.get_by_label("Petugas untuk riwayat", exact=True).fill("Petugas Browser")
    page.get_by_label("Radius pemeriksaan (meter)", exact=True).fill("10")
    page.get_by_role("button", name="Jalankan pemeriksaan", exact=True).click()
    dialog = page.get_by_role("dialog", name="Pemeriksaan koreksi selesai", exact=True)
    expect(dialog).to_be_visible(timeout=20000)
    dialog.get_by_role("button", name="Lihat hasil pemeriksaan", exact=True).click()


def test_not_found_import_conflicts_candidates_missing_coordinates_and_category_isolation(
    page: Page, servers: tuple[str, str]
) -> None:
    prepare(servers[1])
    page.goto("/koreksi/idpel-tidak-ketemu")
    page.get_by_role("button", name="Unggah data koreksi", exact=True).click()
    page.locator("input[type=file]").set_input_files(
        {
            "name": "tidak-ketemu.csv",
            "mimeType": "text/csv",
            "buffer": b"IDPEL,NAMA,LAT,LON\n001,Bentrok,-6.2,106.8\n777,Perlu dicari,-6.2,106.8\n888,Tanpa koordinat,,\n",
        }
    )
    page.get_by_role(
        "button", name="Simpan dan validasi data koreksi", exact=True
    ).click()
    expect(page.get_by_role("status")).to_contain_text("3 baris")
    launch(page)
    cards = page.get_by_role("region", name="Ringkasan IDPEL Tidak Ketemu", exact=True)
    expect(
        cards.get_by_text("Total baris", exact=True)
        .locator("..")
        .get_by_text("3", exact=True)
    ).to_be_visible()
    expect(
        cards.get_by_text("Benturan dengan PDPJ", exact=True)
        .locator("..")
        .get_by_text("1", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
    expect(
        detail.get_by_text("IDPEL sama dengan PDPJ: 001", exact=True)
    ).to_be_visible()
    expect(
        detail.get_by_role("heading", name="Kandidat tersimpan (0)", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Detail koreksi baris 3", exact=True).click()
    expect(
        detail.get_by_role("heading", name="Kandidat tersimpan (7)", exact=True)
    ).to_be_visible()
    expect(detail.get_by_role("article")).to_have_count(7)
    expect(detail.get_by_role("article").first).to_contain_text("002")
    detail.get_by_role("article").first.get_by_text(
        "Detail kandidat dan sumber", exact=True
    ).click()
    expect(detail.get_by_text("dil.csv", exact=True).first).to_be_visible()
    page.get_by_role("button", name="Detail koreksi baris 4", exact=True).click()
    expect(
        detail.get_by_text(
            "Kandidat belum dapat dicari karena koordinat belum lengkap.", exact=True
        )
    ).to_be_visible()
    page.get_by_role(
        "navigation", name="Kategori data koreksi", exact=True
    ).get_by_role("link", name="IDPEL Kosong", exact=True).click()
    cards = page.get_by_role("region", name="Ringkasan IDPEL Kosong", exact=True)
    expect(
        cards.get_by_text("Total baris", exact=True)
        .locator("..")
        .get_by_text("0", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("button", name="Detail koreksi baris 3", exact=True)
    ).to_have_count(0)


def test_mobile_empty_idpel_import_pagination_summary_and_candidate_pages(
    page: Page, servers: tuple[str, str]
) -> None:
    prepare(servers[1], candidates=13)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/koreksi/idpel-kosong")
    page.get_by_role("button", name="Unggah data koreksi", exact=True).click()
    content = "ID_TITIK,NOMOR_METER,LAT,LON\nSURVEY-0,M1,-6.2,106.8\n"
    content += "".join(f"SURVEY-{number},,-6.2,106.8\n" for number in range(1, 31))
    page.locator("input[type=file]").set_input_files(
        {"name": "kosong.csv", "mimeType": "text/csv", "buffer": content.encode()}
    )
    expect(page.get_by_label("Kolom IDPEL", exact=True)).to_have_value("")
    page.get_by_role(
        "button", name="Simpan dan validasi data koreksi", exact=True
    ).click()
    expect(page.get_by_role("status")).to_contain_text("31 baris")
    launch(page)
    cards = page.get_by_role("region", name="Ringkasan IDPEL Kosong", exact=True)
    expect(
        cards.get_by_text("Total baris", exact=True)
        .locator("..")
        .get_by_text("31", exact=True)
    ).to_be_visible()
    expect(
        cards.get_by_text("Kandidat ditemukan", exact=True)
        .locator("..")
        .get_by_text("30", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Halaman koreksi berikutnya", exact=True).click()
    page.get_by_role("button", name="Detail koreksi baris 32", exact=True).click()
    detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
    expect(
        detail.get_by_role("heading", name="Kandidat tersimpan (13)", exact=True)
    ).to_be_visible()
    expect(detail.get_by_role("article")).to_have_count(10)
    detail.get_by_role("button", name="Kandidat berikutnya", exact=True).click()
    expect(detail.get_by_role("article")).to_have_count(3)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_label("Filter hasil koreksi", exact=True).select_option("pdpj_conflict")
    expect(
        page.get_by_role("button", name="Detail koreksi baris 2", exact=True)
    ).to_be_visible()
    expect(
        cards.get_by_text("Total baris", exact=True)
        .locator("..")
        .get_by_text("31", exact=True)
    ).to_be_visible()


def test_radius_retry_preserves_previous_candidate_generation(
    page: Page, servers: tuple[str, str]
) -> None:
    prepare(servers[1])
    batch_id = upload(servers[1], "idpel_kosong", "ID_TITIK,LAT,LON\nONE,-6.2,106.8\n")
    page.goto(f"/koreksi/idpel-kosong?batch_id={batch_id}")
    launch(page)
    page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
    detail = page.get_by_role("region", name="Detail data koreksi", exact=True)
    expect(
        detail.get_by_role("heading", name="Kandidat tersimpan (7)", exact=True)
    ).to_be_visible()
    page.get_by_label("Radius pemeriksaan (meter)", exact=True).fill("100")
    page.get_by_role("button", name="Periksa ulang", exact=True).click()
    dialog = page.get_by_role("dialog", name="Pemeriksaan koreksi selesai", exact=True)
    expect(dialog).to_be_visible(timeout=20000)
    expect(dialog).to_contain_text("versi 2")
    dialog.get_by_role("button", name="Lihat hasil pemeriksaan", exact=True).click()
    page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
    expect(
        detail.get_by_role("heading", name="Kandidat tersimpan (8)", exact=True)
    ).to_be_visible()
    page.get_by_label("Versi hasil", exact=True).select_option("1")
    page.get_by_role("button", name="Detail koreksi baris 2", exact=True).click()
    expect(
        detail.get_by_role("heading", name="Kandidat tersimpan (7)", exact=True)
    ).to_be_visible()
    expect(
        detail.get_by_text("Radius tersimpan 10 m · Versi 1", exact=True)
    ).to_be_visible()
