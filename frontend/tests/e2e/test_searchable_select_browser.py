"""Saved-document options stay visible outside cards and within the viewport."""
import re
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.parametrize("width,height", [(1440, 900), (900, 650), (390, 620)])
def test_saved_document_menu_is_not_clipped_and_keyboard_does_not_scroll_page(
    page: Page, servers: tuple[str, str], tmp_path: Path, width: int, height: int,
) -> None:
    for number in range(1, 19):
        response = httpx.post(servers[1] + "/upload/files", files={"file": (
            f"DATA_KOREKSI_PELANGGAN_DOKUMEN_DENGAN_NAMA_PANJANG_UNTUK_PEMERIKSAAN-{number:02}.csv",
            f"NOAGENDA,LAT,LON\n{number},-6.2,106.8\n".encode(), "text/csv",
        )})
        response.raise_for_status()
    page.set_viewport_size({"width": width, "height": height})
    page.goto("/koreksi/idpel-kosong?flow=upload")
    page.get_by_role("radio", name=re.compile("Gunakan berkas tersimpan")).check()
    field = page.get_by_role("combobox", name="Dokumen tersimpan", exact=True)
    expect(field).to_be_enabled()
    field.click()
    menu = page.get_by_role("listbox", name="Dokumen tersimpan", exact=True)
    expect(menu.get_by_role("option")).to_have_count(18)
    box = menu.bounding_box()
    assert box and box["x"] >= 0 and box["y"] >= 0
    assert box["x"] + box["width"] <= width and box["y"] + box["height"] <= height
    assert menu.evaluate("element => [6, element.clientHeight - 6].every(y => element.contains(document.elementFromPoint(element.getBoundingClientRect().x + element.clientWidth / 2, element.getBoundingClientRect().y + y)))")
    before = page.locator("#main-content").evaluate("element => element.scrollTop")
    field.press("End")
    expect(field).to_have_attribute("aria-activedescendant", re.compile("-option-17$"))
    assert menu.evaluate("element => element.scrollTop > 0")
    assert abs(page.locator("#main-content").evaluate("element => element.scrollTop") - before) <= 1
    field.press("Escape")
    expect(menu).to_have_count(0)
    field.click()
    expect(menu).to_be_visible()
    field.fill("-18.csv")
    expect(menu.get_by_role("option")).to_have_count(1)
    page.screenshot(path=str(tmp_path / f"document-dropdown-{width}.png"))
    print("UI_SCREENSHOT", tmp_path / f"document-dropdown-{width}.png")
    field.press("Enter")
    expect(menu).to_have_count(0)
    expect(field).to_have_value(re.compile("-18.csv"))
    expect(page.get_by_label("Pilih sheet atau tabel", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
