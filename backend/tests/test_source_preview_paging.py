"""Page across source files without sorting/loading their full JSON payloads."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, update
from sqlalchemy.orm import Session

from app.models.upload import SourceRecord, UploadBatch
from tests.test_corrections import upload


@pytest.mark.parametrize(
    "kind", ["prabayar", "pascabayar", "dil", "idpel_kosong", "idpel_tidak_ketemu"]
)
def test_source_preview_pages_cross_files_preserve_scope_and_use_covering_indexes(
    client: TestClient, db_session: Session, kind: str
) -> None:
    first = "" if kind == "idpel_kosong" else "001"
    content = "IDPEL,NAMA,LAT,LON\n" + "".join(
        f"{first},Target {i:03},-6.2,106.8\n" for i in range(35)
    )
    old = upload(client, kind, content)
    new = upload(client, kind, content)
    route = (
        f"/master/{kind}"
        if kind in {"dil", "prabayar", "pascabayar"}
        else f"/corrections/{kind}"
    )
    queries = []

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().startswith("SELECT") and "source_records" in statement:
            queries.append((statement, parameters))

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        response = client.get(route + "/records", params={"skip": 30, "limit": 10})
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)
    assert response.status_code == 200, response.json()
    result = response.json()
    assert result["total"] == 70
    assert [row["batch_id"] for row in result["items"]] == [new] * 5 + [old] * 5
    assert [row["row_number"] for row in result["items"]] == list(range(32, 37)) + list(
        range(2, 7)
    )
    assert not any("source_records.data" in statement for statement, _ in queries)
    identities = [
        (statement, parameters)
        for statement, parameters in queries
        if "LIMIT" in statement and "ORDER BY source_records.id" in statement
    ]
    assert len(identities) == 2
    for statement, parameters in identities:
        plan = (
            db_session.connection()
            .exec_driver_sql("EXPLAIN QUERY PLAN " + statement, parameters)
            .all()
        )
        assert any(
            "USING COVERING INDEX ix_source_records_batch_id_id" in row[3]
            for row in plan
        )
        assert not any("TEMP B-TREE" in row[3] for row in plan)
    filtered = client.get(
        route + "/records", params={"q": "Target 034", "limit": 1}
    ).json()
    assert filtered["total"] == 2 and filtered["items"][0]["batch_id"] == new
    assert (
        client.get(route + "/records", params={"batch_id": old, "skip": 34}).json()[
            "items"
        ][0]["row_number"]
        == 36
    )
    assert client.get(route + "/records", params={"skip": 70}).json()["items"] == []
    assert client.get(route + "/records", params={"q": "%"}).json()["total"] == 0
    detail = client.get(route + f"/records/{result['items'][0]['id']}")
    assert detail.status_code == 200
    assert (detail.json().get("raw_data") or {}).get("NAMA") == "Target 030"


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_correction_preview_keeps_invalid_coordinate_errors(
    client: TestClient, kind: str
) -> None:
    identity = "" if kind == "idpel_kosong" else "001"
    batch = upload(client, kind, f"IDPEL,LAT,LON\n{identity},broken,106.8\n")
    response = client.get(f"/corrections/{kind}/records", params={"batch_id": batch})
    assert response.status_code == 200
    row = response.json()["items"][0]
    assert row["fields"]["lat"] is None
    assert {"field": "lat", "code": "koordinat_tidak_valid"} in row["errors"]


@pytest.mark.parametrize("kind", ["dil", "idpel_kosong"])
def test_legacy_missing_batch_count_uses_database_count(
    client: TestClient, db_session: Session, kind: str
) -> None:
    identity = "" if kind == "idpel_kosong" else "001"
    batch = upload(
        client, kind, "IDPEL,NAMA,LAT,LON\n" + f"{identity},Target,-6.2,106.8\n" * 4
    )
    route = (
        "/master/dil/records" if kind == "dil" else "/corrections/idpel_kosong/records"
    )
    for value in [0, None]:
        db_session.execute(
            update(UploadBatch).where(UploadBatch.id == batch).values(total_rows=value)
        )
        db_session.commit()
        response = client.get(route, params={"batch_id": batch, "skip": 3, "limit": 1})
        assert response.status_code == 200
        assert response.json()["total"] == 4
        assert response.json()["items"][0]["row_number"] == 5


@pytest.mark.parametrize("kind", ["dil", "idpel_kosong", "idpel_tidak_ketemu"])
def test_legacy_and_invalid_pages_load_original_cells_in_one_bounded_query(
    client: TestClient, db_session: Session, kind: str
) -> None:
    identity = "" if kind == "idpel_kosong" else "001"
    batch = upload(client, kind, "IDPEL,LAT,LON\n" + f"{identity},broken,106.8\n" * 20)
    db_session.execute(
        update(SourceRecord)
        .where(SourceRecord.batch_id == batch)
        .values(normalized_data=None)
    )
    db_session.commit()
    db_session.expunge_all()
    originals = []

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        if (
            statement.lstrip().startswith("SELECT")
            and "source_records.data" in statement
        ):
            originals.append((statement, parameters))

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        route = (
            "/master/dil/records" if kind == "dil" else f"/corrections/{kind}/records"
        )
        response = client.get(route, params={"batch_id": batch, "skip": 5, "limit": 10})
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)
    assert response.status_code == 200
    assert response.json()["total"] == 20
    assert len(response.json()["items"]) == 10
    assert all(row["fields"]["lat"] is None for row in response.json()["items"])
    assert len(originals) == 1
    assert len(originals[0][1]) == 10
