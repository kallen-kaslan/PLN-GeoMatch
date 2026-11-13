"""Real map interactions, stored-radius reuse, choices, and responsive fallback."""

from workspace_controls import open_radius_controls, open_map_context

import httpx
import re
from urllib.parse import parse_qs, urlparse
import pytest
from playwright.sync_api import Page, Route, expect
from test_corrections_browser import prepare, upload


def setup_map(
    page: Page,
    api_url: str,
    kind: str = "idpel_kosong",
    count: int = 27,
    stacked: bool = True,
) -> tuple[int, int]:
    review = prepare(api_url, candidates=12)
    content = (
        "IDPEL,NAMA,LAT,LON\n"
        + "".join(
            f"{'' if kind == 'idpel_kosong' else 700 + number},Target {number},{-6.2 if stacked else -6.2 - (number - 1) * 0.0005},106.8\n"
            for number in range(1, count + 1)
        )
        + f"{'' if kind == 'idpel_kosong' else 999},Tanpa koordinat,,\n"
    )
    batch = upload(api_url, kind, content)
    response = httpx.post(
        f"{api_url}/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review,
            "radius_meters": 10,
            "actor": "Petugas Browser",
            "request_key": "map_browser_start",
        },
        timeout=30,
    )
    response.raise_for_status()
    process = response.json()["process_id"]
    page.goto(f"/peta-koreksi?category={kind}&batch_id={batch}&process_id={process}")
    expect(
        page.get_by_text(
            f"{count + 1} baris · {count} bertitik · 1 tanpa koordinat", exact=False
        )
    ).to_be_visible(timeout=20000)
    return batch, process


def test_map_all_points_hover_selection_and_candidate_pagination(
    page: Page, servers: tuple[str, str]
) -> None:
    setup_map(page, servers[1], count=127)
    expect(page.get_by_role("button", name="Tampilkan kandidat target", exact=True)).to_have_count(0)
    # Load all API pages (>100 rows), independently of the 25-row table page.
    point = page.get_by_role("button", name="127 target bertumpuk", exact=True)
    expect(point).to_be_visible(timeout=20000)
    point.hover()
    tooltip = page.locator(".leaflet-tooltip")
    expect(tooltip).to_contain_text("127 target pada titik ini")
    page.get_by_role("heading", name="Peta Koreksi", exact=True).hover()
    expect(tooltip).not_to_be_visible()
    point.click()
    page.get_by_role("button", name="Pilih baris 128 · Target 127", exact=True).click()
    expect(
        page.get_by_role("region", name="Detail target terpilih", exact=True)
    ).to_contain_text("Target 127")
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("12 kandidat tersimpan", timeout=20000)
    expect(candidates.get_by_role("article")).to_have_count(10)
    candidates.get_by_role("button", name="Kandidat berikutnya", exact=True).click()
    expect(candidates.get_by_role("article")).to_have_count(2)
    page.get_by_role("button", name="Halaman peta berikutnya", exact=True).click()
    page.get_by_label("Cari target peta", exact=True).fill("Tanpa koordinat")
    page.get_by_role("button", name="Pilih target baris 129", exact=True).click()
    expect(page.get_by_role("region", name="Kandidat target peta", exact=True)).to_have_count(0)
    expect(
        page.get_by_role("region", name="Detail target terpilih", exact=True)
    ).to_contain_text("belum mempunyai koordinat lengkap")


def test_map_highlights_selected_target_and_links_candidate_to_later_card_page(
    page: Page, servers: tuple[str, str]
) -> None:
    setup_map(page, servers[1], count=2, stacked=False)
    point = page.get_by_role("button", name="Titik koreksi baris 2", exact=True)
    point.click()
    expect(
        page.get_by_role("button", name="Titik koreksi baris 2", exact=True)
    ).to_have_attribute("fill", "#2563eb")
    expect(
        page.get_by_role("button", name="Titik koreksi baris 3", exact=True)
    ).to_have_attribute("fill", "#9ca3af")

    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("12 kandidat tersimpan", timeout=20000)
    page.locator(".leaflet-overlay-pane path[fill='#22c55e']").click()
    page.get_by_role("button", name="Kandidat 12 · 013 · 0.00 m", exact=True).click()
    expect(candidates).to_contain_text("Halaman kandidat 2 dari 2")
    expect(
        candidates.get_by_role("article", name="Kandidat peta 12", exact=True)
    ).to_be_focused()


def test_choose_replace_radius_expansion_history_and_category_isolation(
    page: Page, servers: tuple[str, str]
) -> None:
    batch, process = setup_map(page, servers[1], kind="idpel_tidak_ketemu", count=2)
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    expect(page.get_by_label("Petugas peta", exact=True)).to_have_value("test-admin")
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("12 kandidat tersimpan", timeout=20000)
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    detail = page.get_by_role("region", name="Detail target terpilih", exact=True)
    expect(detail).to_contain_text("Pilihan aktif: 002", timeout=10000)
    expect(
        candidates.get_by_role("button", name="Pilih kandidat 2", exact=True)
    ).to_be_disabled()
    page.get_by_label("Alasan perubahan pilihan", exact=True).fill(
        "Meter pada kandidat kedua lebih sesuai"
    )
    candidates.get_by_role("button", name="Pilih kandidat 2", exact=True).click()
    expect(detail).to_contain_text("Pilihan aktif: 003", timeout=10000)
    detail.get_by_text("Riwayat pilihan (2)", exact=True).click()
    expect(detail).to_contain_text("IDPEL 002")
    open_radius_controls(page)
    page.get_by_label("Radius perluasan (meter)", exact=True).fill("100")
    page.get_by_role(
        "button", name="Perluas pemeriksaan dan tampilkan kandidat", exact=True
    ).click()
    expect(candidates).to_contain_text("13 kandidat tersimpan", timeout=30000)
    expect(
        page.get_by_role("region", name="Progres pemeriksaan koreksi")
    ).to_have_count(0)
    expect(detail).to_contain_text("Pilihan aktif: 003")
    page.get_by_label("Radius peta (meter)", exact=True).fill("1")
    expect(candidates).to_contain_text("12 kandidat tersimpan", timeout=15000)
    assert (
        len(
            httpx.get(
                f"{servers[1]}/corrections/idpel_tidak_ketemu/checks/{process}"
            ).json()["runs"]
        )
        == 2
    )
    page.goto(
        f"/peta-koreksi?category=idpel_tidak_ketemu&batch_id={batch}&process_id={process}&generation=1"
    )
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    expect(
        page.get_by_text("Anda melihat versi historis 1.", exact=False)
    ).to_be_visible()
    expect(
        page.get_by_role("button", name="Batalkan pilihan", exact=True)
    ).to_be_disabled()
    open_map_context(page)
    page.get_by_label("Kategori peta", exact=True).select_option("idpel_kosong")
    expect(
        page.get_by_role("region", name="Tabel target peta", exact=True)
    ).not_to_contain_text("Target 1")


def test_map_unavailable_keeps_mobile_table_and_choice_flow(
    page: Page, servers: tuple[str, str]
) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.route("**/leaflet.js", lambda route: route.abort())
    setup_map(page, servers[1], count=1)
    expect(page.get_by_text("Peta belum dapat dimuat.", exact=False)).to_be_visible()
    page.get_by_role("tab", name="Daftar", exact=True).click()
    page.get_by_role("button", name="Pilih target baris 2", exact=True).click()

    expect(
        page.get_by_role("region", name="Kandidat target peta", exact=True)
    ).to_contain_text("12 kandidat tersimpan", timeout=20000)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_select_target_loads_candidates_automatically_and_preserves_read_only_flow(
    page: Page, servers: tuple[str, str]
) -> None:
    _, process = setup_map(page, servers[1], count=2, stacked=False)
    requests: list[Route] = []
    candidate_url = re.compile(r"/corrections/idpel_kosong/records/\d+\?.*radius_meters=")
    page.route(candidate_url, lambda route: requests.append(route))
    with page.expect_request(candidate_url):
        page.get_by_role("button", name="Pilih target baris 2", exact=True).click()
    panel = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(panel).to_have_attribute("aria-busy", "true")
    expect(panel.get_by_role("status")).to_contain_text("Memuat kandidat")
    expect(panel.get_by_text("0 kandidat tersimpan", exact=False)).to_have_count(0)
    assert requests
    requests[0].continue_()
    page.unroute(candidate_url)
    expect(panel).to_contain_text("12 kandidat tersimpan")
    expect(panel).to_have_attribute("aria-busy", "false")
    page.get_by_role("button", name="Pilih target baris 3", exact=True).click()
    expect(panel).to_contain_text("1 kandidat tersimpan")
    expect(panel.get_by_role("article")).to_have_count(1)
    expect(panel.get_by_role("article")).to_contain_text("099")
    expect(page.get_by_role("button", name="Titik koreksi baris 3", exact=True)).to_have_attribute("fill", "#2563eb")
    map_box = page.get_by_role("region", name="Pemetaan koreksi", exact=True).bounding_box()
    assert map_box and 0 <= map_box["y"] < page.viewport_size["height"] / 3
    page.reload()
    expect(panel).to_contain_text("1 kandidat tersimpan")
    expect(panel.get_by_role("article")).to_contain_text("099")
    history = httpx.get(f"{servers[1]}/corrections/idpel_kosong/checks/{process}/results/history")
    history.raise_for_status()
    assert history.json()["total"] == 0
    # A row without coordinates exposes its explanation without issuing a candidate request.
    rejected_requests: list[Route] = []
    page.route(candidate_url, lambda route: (rejected_requests.append(route), route.continue_()))
    page.get_by_role("button", name="Pilih target baris 4", exact=True).click()
    expect(page.get_by_role("region", name="Detail target terpilih", exact=True)).to_contain_text("belum mempunyai koordinat lengkap")
    expect(panel).to_have_count(0)
    assert not rejected_requests


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_clear_target_keeps_saved_decision_filters_and_table_page(
    page: Page, servers: tuple[str, str], kind: str,
) -> None:
    _, process = setup_map(page, servers[1], kind=kind, count=30)
    page.get_by_label("Cari target peta", exact=True).fill("Target")
    page.get_by_label("Filter hasil peta", exact=True).select_option("matched")
    expect(page).to_have_url(re.compile(r"[?&]status=matched(?:&|$)"))
    radius = page.get_by_label("Radius peta (meter)", exact=True)
    radius.fill("1")
    expect(page.get_by_role("region", name="Ringkasan radius peta", exact=True)).to_contain_text("Radius 1 m")
    expect(page.get_by_label("Filter hasil peta", exact=True)).to_have_value("matched")
    jump = page.get_by_label("Nomor halaman peta", exact=True)
    jump.fill("2")
    jump.press("Enter")
    page.get_by_role("button", name="Pilih target baris 27", exact=True).click()
    candidates = page.get_by_role("region", name="Kandidat target peta", exact=True)
    expect(candidates).to_contain_text("12 kandidat tersimpan")
    expect(page.get_by_label("Petugas peta", exact=True)).to_have_value("test-admin")
    candidates.get_by_role("button", name="Pilih kandidat 1", exact=True).click()
    detail = page.get_by_role("region", name="Detail target terpilih", exact=True)
    expect(detail).to_contain_text("Pilihan aktif: 002")
    before = parse_qs(urlparse(page.url).query)
    record_id = before["record_id"][0]
    choice_url = f"{servers[1]}/corrections/{kind}/checks/{process}/records/{record_id}/choice"
    saved = httpx.get(choice_url).json()
    assert saved["current"]["candidate_id"]

    page.locator(".geo-map-dock > summary").click()
    page.get_by_role("button", name="Lepas pilihan target", exact=True).click()
    expect(detail).to_have_count(0)
    expect(candidates).to_have_count(0)
    table = page.get_by_role("region", name="Tabel target peta", exact=True)
    expect(table.locator('tr[aria-selected="true"]')).to_have_count(0)
    expect(page.get_by_role("heading", name=f"Target {'IDPEL Kosong' if kind == 'idpel_kosong' else 'IDPEL Tidak Ketemu'}", exact=True)).to_be_focused()
    expect(jump).to_have_value("2")
    expect(page.get_by_label("Cari target peta", exact=True)).to_have_value("Target")
    expect(page.get_by_label("Filter hasil peta", exact=True)).to_have_value("matched")
    expect(radius).to_have_value("1")
    expect(page.locator(".leaflet-overlay-pane path[fill='#2563eb']")).to_have_count(0)
    after = parse_qs(urlparse(page.url).query)
    assert "record_id" not in after
    for key in ("category", "batch_id", "process_id", "generation", "radius_meters", "status"):
        assert after.get(key) == before.get(key)
    assert httpx.get(choice_url).json() == saved

    page.reload()
    expect(candidates).to_have_count(0)
    expect(detail).to_have_count(0)
    expect(radius).to_have_value("1")
    jump.fill("2")
    jump.press("Enter")
    page.get_by_role("button", name="Pilih target baris 27", exact=True).click()
    expect(candidates).to_contain_text("12 kandidat tersimpan")
    expect(detail).to_contain_text("Pilihan aktif: 002")
    assert httpx.get(choice_url).json() == saved


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_map_preview_page_input_sizes_filters_and_mobile(
    page: Page, servers: tuple[str, str], kind: str
) -> None:
    setup_map(page, servers[1], kind=kind, count=105)
    table = page.get_by_role("region", name="Tabel target peta", exact=True)
    footer = table.get_by_label("Navigasi halaman peta", exact=True)
    jump = footer.get_by_label("Nomor halaman peta", exact=True)
    size = footer.get_by_label("Baris per halaman peta", exact=True)
    expect(table.get_by_role("row")).to_have_count(26)
    expect(size).to_have_value("25")
    jump.fill("4")
    jump.press("Enter")
    expect(footer).to_contain_text("Menampilkan 76–100. Halaman 4 dari 5")
    expect(
        table.get_by_role("button", name="Pilih target baris 77", exact=True)
    ).to_be_visible()
    footer.get_by_role("button", name="Halaman peta berikutnya", exact=True).click()
    expect(table.get_by_role("row")).to_have_count(7)
    jump.fill("6")
    footer.get_by_role("button", name="Buka halaman", exact=True).click()
    expect(footer.get_by_role("alert")).to_have_text(
        "Masukkan nomor halaman antara 1 dan 5."
    )
    jump.fill("1.5")
    jump.press("Enter")
    expect(footer.get_by_role("alert")).to_be_visible()
    for rows in (50, 100, 10, 25):
        size.select_option(str(rows))
        expect(table.get_by_role("row")).to_have_count(rows + 1)
        expect(jump).to_have_value("1")
        expect(footer.get_by_role("alert")).to_have_count(0)
    jump.fill("5")
    footer.get_by_role("button", name="Buka halaman", exact=True).click()
    page.get_by_label("Cari target peta", exact=True).fill("Target 105")
    expect(table.get_by_role("row")).to_have_count(2)
    expect(jump).to_have_count(0)
    expect(footer).to_contain_text("Halaman 1 dari 1")
    page.get_by_label("Filter hasil peta", exact=True).select_option("no_candidates")
    expect(footer).to_contain_text("0 baris sesuai filter")
    expect(jump).to_have_count(0)
    page.get_by_label("Cari target peta", exact=True).fill("")
    page.get_by_label("Filter hasil peta", exact=True).select_option("all")
    jump.fill("4")
    jump.press("Enter")
    page.get_by_label("Radius peta (meter)", exact=True).fill("1")
    expect(jump).to_have_value("1")
    expect(footer).to_contain_text("Menampilkan 1–25")
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("tab", name="Daftar", exact=True).click()
    expect(jump).to_be_visible()
    expect(size).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
