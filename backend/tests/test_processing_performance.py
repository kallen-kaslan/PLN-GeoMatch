"""Performance changes must retain data, evidence associations and API responsiveness."""

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import perf_counter

import pytest
from sqlalchemy import event, inspect

from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.matching import MatchCandidate
from app.modules.pdpj import router as pdpj_router
from app.modules.upload import normalization as norm
from app.performance import logger, timed
from app.performance_schema import INDEX_COLUMNS, upgrade_performance
from tests.test_corrections import check, upload
from tests.test_corrections import reference as _reference

reference = _reference


def test_indexes_upgrade_old_database_without_losing_data(db_session):
    connection = db_session.connection()
    for table, indexes in INDEX_COLUMNS.items():
        for name, _ in indexes:
            connection.exec_driver_sql(f'DROP INDEX "{name}"')
    connection.exec_driver_sql("ALTER TABLE upload_batches DROP COLUMN source_headers")
    connection.exec_driver_sql(
        "INSERT INTO upload_batches (id, filename) VALUES (1, 'source.csv')"
    )
    connection.exec_driver_sql(
        "INSERT INTO source_records (batch_id, idpel, data, is_valid) VALUES (1, '000123', '{\"IDPEL\":\"000123\"}', 1)"
    )
    before = connection.exec_driver_sql("SELECT idpel, data FROM source_records").all()
    upgrade_performance(connection)
    upgrade_performance(connection)
    assert (
        connection.exec_driver_sql("SELECT idpel, data FROM source_records").all()
        == before
    )
    assert "source_headers" in {
        column["name"] for column in inspect(connection).get_columns("upload_batches")
    }
    for table, indexes in INDEX_COLUMNS.items():
        actual = {item["name"] for item in inspect(connection).get_indexes(table)}
        assert all(name in actual for name, _ in indexes)
    plan = connection.exec_driver_sql(
        "EXPLAIN QUERY PLAN SELECT id FROM source_records WHERE batch_id=1 ORDER BY id LIMIT 400"
    ).all()
    assert any("SEARCH" in row[3] and "batch_id" in row[3] for row in plan)


def test_column_plan_preserves_dynamic_blank_aliases_and_explicit_mapping():
    def original(data, mapping):
        normalized = {
            norm.normalize_column_name(key): value for key, value in data.items()
        }
        selected = norm.canonical_mapping(mapping)
        return {
            name: data.get(selected[name])
            if name in selected
            else next(
                (
                    normalized[key]
                    for key in aliases
                    if norm.clean_text(normalized.get(key))
                ),
                None,
            )
            for name, aliases in norm.ALIASES.items()
        }

    mappings = [
        None,
        {"idpel": "CUSTOMER", "lat": "CUSTOM_Y", "lon": "CUSTOM_X"},
        {"IDPELANGGAN": "IDPEL", "nama": "NAMA"},
    ]
    for i in range(30):
        row = {
            "IDPEL": "000123" if i % 2 else "",
            "id-pel": "000999" if i % 3 else "",
            "IDPELANGGAN": "000456",
            "CUSTOMER": "000789",
            "NAMA": "Nama",
            "LAT": "" if i % 2 else "-6.2",
            "LATITUDE": "-7.0",
            "CUSTOM_Y": "",
            "CUSTOM_X": "106.8",
        }
        for mapping in mappings:
            assert norm.raw_fields(row, mapping) == original(row, mapping)
    first = norm.canonical_mapping({"idpel": "IDPEL"})
    first["idpel"] = "Changed"
    assert norm.canonical_mapping({"idpel": "IDPEL"}) == {"idpel": "IDPEL"}


def test_bulk_candidates_keep_correct_evidence_even_if_returning_order_changes(
    client,
    reference,
    db_session,
    monkeypatch,
):
    batch_id = upload(
        client,
        "idpel_kosong",
        "ID_TITIK,LAT,LON\n" + "".join(f"TARGET-{i},-6.2,106.8\n" for i in range(123)),
    )
    counts = {"candidates": 0, "evidence": 0}

    def count_inserts(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO match_candidates"):
            counts["candidates"] += 1
        if statement.startswith("INSERT INTO correction_candidate_evidence"):
            counts["evidence"] += 1

    execute = db_session.execute

    def reverse_returning(statement, *args, **kwargs):
        result = execute(statement, *args, **kwargs)
        if (
            getattr(getattr(statement, "table", None), "name", None)
            == "match_candidates"
        ):
            return iter(reversed(result.all()))
        return result

    monkeypatch.setattr(db_session, "execute", reverse_returning)
    event.listen(db_session.get_bind(), "after_cursor_execute", count_inserts)
    try:
        result = check(client, "idpel_kosong", batch_id, reference)
    finally:
        event.remove(db_session.get_bind(), "after_cursor_execute", count_inserts)
    pairs = (
        db_session.query(MatchCandidate, CorrectionCandidateEvidence)
        .join(CorrectionCandidateEvidence)
        .filter(MatchCandidate.process_id == result["process_id"])
        .all()
    )
    assert len(pairs) == 123 * 7
    for candidate, evidence in pairs:
        assert candidate.candidate_idpel == evidence.fields["idpel"]
        assert evidence.observations[0]["fields"]["idpel"] == candidate.candidate_idpel
        assert candidate.candidate_idpel == f"{candidate.rank + 1:03}"
    assert (
        db_session.query(CorrectionTarget)
        .filter_by(
            run_id=result["latest_run"]["id"],
            candidate_count=7,
            search_status="matched",
        )
        .count()
        == 123
    )
    assert 0 < counts["candidates"] < 10 and 0 < counts["evidence"] < 10, counts


def test_heavy_pdpj_request_does_not_block_unrelated_api(client, monkeypatch):
    started, release = Event(), Event()

    def slow_review(*args):
        started.set()
        assert release.wait(8)
        return object()

    async def ping():
        return {"ok": True}

    client.app.add_api_route("/_performance_ping", ping)
    monkeypatch.setattr(pdpj_router, "create_review", slow_review)
    monkeypatch.setattr(pdpj_router, "review_info", lambda _: {"id": 1})
    with ThreadPoolExecutor() as pool:
        task = pool.submit(client.post, "/pdpj/reviews", json={"batch_id": 1})
        try:
            assert started.wait(3)
            now = perf_counter()
            assert client.get("/_performance_ping").json() == {"ok": True}
            assert perf_counter() - now < 2
        finally:
            release.set()
        assert task.result().status_code == 200


def test_stage_timing_never_logs_cells_or_exception_messages(caplog, monkeypatch):
    monkeypatch.setattr(logger, "disabled", False)
    caplog.set_level(logging.INFO, logger=logger.name)

    @timed("test.success")
    def operation(batch_id, private_value):
        return {"rows": 2, "raw_data": private_value}

    assert operation(7, "PRIVATE-CUSTOMER-NAME")["rows"] == 2
    assert "duration_ms=" in caplog.text and "batch_id" in caplog.text
    assert "PRIVATE-CUSTOMER-NAME" not in caplog.text

    @timed("test.failure")
    def fail():
        raise ValueError("PRIVATE-EXCEPTION-DATA")

    with pytest.raises(ValueError):
        fail()
    assert "status=failed" in caplog.text
    assert "PRIVATE-EXCEPTION-DATA" not in caplog.text


def test_pdpj_ingestion_detects_duplicates_across_chunks_and_carries_changes(client):
    master = "IDPEL,NAMA,LAT,LON\n" + "".join(
        f"{i:06},Nama {i},-6.2,106.8\n" for i in range(1, 403)
    )
    upload(client, "dil", master)
    pdpj = (
        "IDPEL,NAMA,LAT,LON\n"
        + "".join(f"{i:06},Nama {i},-6.2,106.8\n" for i in range(1, 403))
        + "000001,Duplikat,-6.2,106.8\n"
    )
    batch_id = upload(client, "pdpj", pdpj)
    created = client.post("/pdpj/reviews", json={"batch_id": batch_id})
    assert created.status_code == 200, created.text
    first = created.json()
    summary = client.get(f"/pdpj/reviews/{first['id']}").json()
    assert summary["summary"]["total_rows"] == 403
    assert summary["summary"]["found"] == 403
    assert summary["summary"]["unresolved"] == 0
    duplicates = client.get(
        f"/pdpj/reviews/{first['id']}/rows", params={"q": "000001"}
    ).json()["items"]
    assert len(duplicates) == 2 and all(
        row["warnings"] and not row["issues"] for row in duplicates
    )
    row = client.get(f"/pdpj/reviews/{first['id']}/rows").json()["items"][0]
    edited = client.patch(
        f"/pdpj/reviews/{first['id']}/rows/{row['id']}",
        json={
            "revision": summary["revision"],
            "actor": "Petugas Uji",
            "reason": "Uji nilai lintas batch",
            "fields": {"nama": "Nama diperbaiki"},
        },
    )
    assert edited.status_code == 200, edited.text
    completed = client.post(
        f"/pdpj/reviews/{first['id']}/complete",
        json={
            "revision": edited.json()["revision"],
            "actor": "Petugas Uji",
        },
    )
    assert completed.status_code == 200, completed.text
    again = client.post("/pdpj/reviews", json={"batch_id": batch_id}).json()
    new_row = client.get(f"/pdpj/reviews/{again['id']}/rows").json()["items"][0]
    detail = client.get(f"/pdpj/reviews/{again['id']}/rows/{new_row['id']}").json()
    assert detail["fields"]["nama"] == "Nama diperbaiki"
    assert detail["recommendations_total"] == 1
    assert any(
        change["action"] == "carried_forward"
        and change["sources"]["previous_review_id"] == first["id"]
        for change in detail["history"]
    )
    assert (
        client.get(f"/pdpj/reviews/{again['id']}").json()["summary"]["unresolved"] == 0
    )
    changed_identity = client.patch(
        f"/pdpj/reviews/{again['id']}/rows/{new_row['id']}",
        json={
            "revision": again["revision"],
            "actor": "Petugas Uji",
            "reason": "Perbaikan identitas asal",
            "fields": {"idpel": "000999"},
        },
    )
    assert changed_identity.status_code == 200, changed_identity.text
    unresolved = client.get(
        f"/pdpj/reviews/{again['id']}/rows", params={"status": "unresolved"}
    ).json()
    assert unresolved["total"] == 1
    assert unresolved["items"][0]["fields"]["idpel"] == "000999"
    formerly_duplicate = client.get(
        f"/pdpj/reviews/{again['id']}/rows", params={"q": "000001"}
    ).json()["items"]
    assert len(formerly_duplicate) == 1 and formerly_duplicate[0]["issues"] == []
