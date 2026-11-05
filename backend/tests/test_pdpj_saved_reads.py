"""Unchanged PDPJ reads reuse counters; edits and processing revisions stay fresh."""

from typing import Any

from app.models.pdpj import PDPJ_SUMMARY_INDEX, PdpjRow
from app.pdpj_summary_schema import upgrade_pdpj_summary
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from tests.test_pdpj_validation import upload


def prepare(client: TestClient, content: str) -> dict:
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.3,106.9\n")
    batch = upload(client, "pdpj", content)
    result = client.post("/pdpj/reviews", json={"batch_id": batch})
    assert result.status_code == 200, result.text
    return result.json()


def capture_rows(db: Session, request: Any) -> tuple[Any, list[tuple[str, Any]]]:
    reads = []

    def capture(
        _conn: Any, _cursor: Any, sql: str, parameters: Any, _context: Any, _many: Any
    ) -> None:
        if sql.lstrip().startswith("SELECT") and "pdpj_rows" in sql:
            reads.append((sql, parameters))

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        return request(), reads
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)


def test_first_summary_uses_covering_index_and_unchanged_reads_skip_row_counts(
    client: TestClient, db_session: Session
) -> None:
    review = prepare(
        client,
        "IDPEL,NAMA,LAT,LON\n001,Lengkap,-6.2,106.8\n002,Belum lengkap,,\n999,Tidak ketemu,-6.2,106.8\n",
    )
    path = f"/pdpj/reviews/{review['id']}"
    # The saved processing checkpoint already knows the unfiltered table total.
    rows, reads = capture_rows(db_session, lambda: client.get(path + "/rows"))
    assert rows.json()["total"] == 3
    assert not any("count(" in sql.lower() for sql, _ in reads)
    summary, reads = capture_rows(db_session, lambda: client.get(path))
    assert summary.status_code == 200
    counts = summary.json()["summary"]
    assert counts["found"] == 2 and counts["not_found"] == 1
    assert counts["incomplete_coordinates"] == 1
    assert len(reads) == 1
    sql, params = reads[0]
    assert "pdpj_rows.current_fields" in sql and "pdpj_rows.original_fields" not in sql
    plan = (
        db_session.connection()
        .exec_driver_sql("EXPLAIN QUERY PLAN " + sql, params)
        .all()
    )
    assert any(
        f"USING COVERING INDEX {PDPJ_SUMMARY_INDEX}" in item[3] for item in plan
    ), plan
    db_session.expunge_all()
    repeated, reads = capture_rows(db_session, lambda: client.get(path))
    assert repeated.json()["summary"] == counts
    assert reads == []
    for status, total in [
        ("all", 3),
        ("found", 2),
        ("not_found", 1),
        ("incomplete", 1),
        ("ready", 1),
        ("unresolved", 2),
    ]:
        response, reads = capture_rows(
            db_session,
            lambda status=status: client.get(path + "/rows", params={"status": status}),
        )
        assert response.json()["total"] == total
        assert not any("count(" in sql.lower() for sql, _ in reads)
    searched = client.get(
        path + "/rows", params={"q": "Tidak ketemu", "status": "found"}
    ).json()
    assert searched["total"] == 0 and searched["items"] == []


def test_summary_refreshes_after_edit_exception_and_completion(
    client: TestClient, db_session: Session
) -> None:
    review = prepare(client, "IDPEL,LAT,LON\n001,-6.2,106.8\n002,,\n999,-6.2,106.8\n")
    path = f"/pdpj/reviews/{review['id']}"
    before = client.get(path).json()
    rows = client.get(path + "/rows").json()["items"]
    fixed = client.patch(
        path + f"/rows/{rows[1]['id']}",
        json={
            "revision": before["revision"],
            "actor": "Petugas",
            "fields": {"lat": -6.3, "lon": 106.9},
            "reason": "Verifikasi lapangan",
        },
    )
    assert fixed.status_code == 200, fixed.text
    after, reads = capture_rows(db_session, lambda: client.get(path))
    fresh = after.json()
    assert reads and fresh["revision"] > before["revision"]
    assert fresh["summary"]["incomplete_coordinates"] == 0
    assert fresh["summary"]["unresolved"] == 1
    assert fresh["summary"]["ready"] == 2
    decided = client.post(
        path + f"/rows/{rows[2]['id']}/decision",
        json={
            "revision": fresh["revision"],
            "actor": "Petugas",
            "action": "exception",
            "reason": "Referensi belum tersedia",
        },
    )
    assert decided.status_code == 200, decided.text
    fresh = client.get(path).json()
    assert fresh["summary"]["unresolved"] == 0 and fresh["summary"]["exceptions"] == 1
    completed = client.post(
        path + "/complete", json={"revision": fresh["revision"], "actor": "Petugas"}
    )
    assert completed.status_code == 200, completed.text
    summary = client.get(path).json()
    assert summary["status"] == "completed"
    assert summary["summary"]["ready"] == 2 and summary["summary"]["exceptions"] == 1


def test_reset_with_reused_ids_and_revisions_does_not_reuse_old_summary(
    client: TestClient,
) -> None:
    first = prepare(client, "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.3,106.9\n")
    assert client.get(f"/pdpj/reviews/{first['id']}").json()["summary"]["found"] == 2
    assert client.post("/upload/reset").status_code == 200
    second = prepare(client, "IDPEL,LAT,LON\n998,-6.2,106.8\n999,-6.3,106.9\n")
    assert first["id"] == second["id"] and first["revision"] == second["revision"]
    result = client.get(f"/pdpj/reviews/{second['id']}").json()["summary"]
    assert result["found"] == 0 and result["not_found"] == 2


def test_summary_cache_follows_processing_checkpoints(
    client: TestClient, monkeypatch: Any
) -> None:
    from app.modules.pdpj import service

    monkeypatch.setattr(service, "VALIDATION_CHUNK_ROWS", 2)
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    batch = upload(
        client,
        "pdpj",
        "IDPEL,LAT,LON\n001,-6.2,106.8\n001,-6.3,106.9\n999,-6.2,106.8\n",
    )
    review = client.post(
        "/pdpj/reviews", json={"batch_id": batch, "incremental": True}
    ).json()
    path = f"/pdpj/reviews/{review['id']}"
    assert client.get(path).json()["summary"]["total_rows"] == 0
    review = client.post(
        path + "/advance", json={"revision": review["revision"]}
    ).json()
    assert client.get(path).json()["summary"]["total_rows"] == 2
    paused = client.post(path + "/pause").json()
    assert client.get(path).json()["summary"]["total_rows"] == 2
    review = client.post(path + "/resume").json()
    assert review["revision"] > paused["revision"]
    for _ in range(8):
        if review["processing"]["state"] == "ready":
            break
        review = client.post(
            path + "/advance", json={"revision": review["revision"]}
        ).json()
    assert review["processing"]["state"] == "ready"
    counts = client.get(path).json()["summary"]
    assert (
        counts["total_rows"] == 3 and counts["found"] == 2 and counts["not_found"] == 1
    )


def test_summary_index_upgrade_preserves_rows_and_can_repeat(
    client: TestClient, db_session: Session
) -> None:
    prepare(client, "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    table = PdpjRow.__table__
    before = db_session.execute(table.select()).all()
    connection = db_session.connection()
    next(index for index in table.indexes if index.name == PDPJ_SUMMARY_INDEX).drop(
        connection
    )
    upgrade_pdpj_summary(connection)
    upgrade_pdpj_summary(connection)
    assert PDPJ_SUMMARY_INDEX in {
        row[1] for row in connection.exec_driver_sql("PRAGMA index_list('pdpj_rows')")
    }
    assert db_session.execute(table.select()).all() == before
