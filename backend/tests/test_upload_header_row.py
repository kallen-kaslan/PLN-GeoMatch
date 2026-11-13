"""Header detection skips the title rows some DIL exports write above the columns."""

from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.modules.upload.reader import header_row_index


def test_header_row_index_prefers_the_row_naming_several_columns() -> None:
    rows = [["LAPORAN DIL"], ["tanggal cetak"], ["IDPEL", "NAMA", "LAT", "LON"], ["001"]]
    assert header_row_index(rows) == 2
    # Without a multi-column row, the first named row is used, like the frontend preview.
    assert header_row_index([["IDPEL"], ["001"]]) == 0
    assert header_row_index([[""], ["   "]]) is None


def workbook(rows: list[list[object]]) -> bytes:
    book = Workbook()
    for row in rows:
        book.active.append(row)
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def test_title_rows_above_the_header_are_skipped(client: TestClient) -> None:
    content = workbook(
        [
            ["LAPORAN DATA INDUK PELANGGAN"],
            ["Periode Januari 2026"],
            [],
            ["IDPEL", "NAMA", "LAT", "LON"],
            ["001", "Pelanggan A", -6.2, 106.8],
            ["002", "Pelanggan B", -6.3, 106.9],
        ]
    )
    stored = client.post("/upload/files", files={"file": ("dil.xlsx", content)})
    assert stored.status_code == 200, stored.text
    file_id = stored.json()["id"]

    preview = client.get(
        f"/upload/files/{file_id}/preview", params={"sheet_name": "Sheet"}
    )
    assert preview.status_code == 200, preview.text
    assert [row["IDPEL"] for row in preview.json()["rows"]] == ["001", "002"]

    imported = client.post(
        f"/upload/files/{file_id}/import-sheet",
        json={"dataset_type": "dil", "sheet_name": "Sheet"},
    )
    assert imported.status_code == 200, imported.text
    batch = imported.json()
    assert (
        client.get(f"/master/dil/batches/{batch['id']}").json()["headers"]
        == ["IDPEL", "NAMA", "LAT", "LON"]
    )

    # The mapping the frontend offers from its own preview must be accepted.
    confirmed = client.post(
        "/upload/confirm-mapping",
        json={
            "batch_id": batch["id"],
            "column_mapping": {"idpel": "IDPEL", "lat": "LAT", "lon": "LON"},
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["valid_rows"] == 2


def test_early_title_row_within_the_scan_window(client: TestClient) -> None:
    content = workbook([["JUDUL"]] * 20 + [["IDPEL", "NAMA"], ["001", "A"]])
    stored = client.post("/upload/files", files={"file": ("far.xlsx", content)})
    assert stored.status_code == 200, stored.text
    imported = client.post(
        f"/upload/files/{stored.json()['id']}/import-sheet",
        json={"dataset_type": "dil", "sheet_name": "Sheet"},
    )
    assert imported.status_code == 200, imported.text
    assert (
        client.get(f"/master/dil/batches/{imported.json()['id']}").json()["headers"]
        == ["IDPEL", "NAMA"]
    )


def test_sheet_without_any_named_cell_is_rejected(client: TestClient) -> None:
    content = workbook([[], ["   "], [None]])
    stored = client.post("/upload/files", files={"file": ("notes.xlsx", content)})
    assert stored.status_code == 200, stored.text
    imported = client.post(
        f"/upload/files/{stored.json()['id']}/import-sheet",
        json={"dataset_type": "dil", "sheet_name": "Sheet"},
    )
    assert imported.status_code == 400, imported.text
