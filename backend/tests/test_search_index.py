"""Indexed search preserves literal substring semantics and tracks transactional edits."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import search_index
from app.database import Base
from app.models.pdpj import PdpjRow
from app.models.upload import DatasetType, SourceRecord, UploadBatch
from app.sqlite_runtime import configure_sqlite_engine
from tests import test_correction_results
from tests.test_corrections import upload

partial = test_correction_results.partial


@pytest.fixture
def db_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'search.db').as_posix()}")
    configure_sqlite_engine(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    deadline = time.monotonic() + 5
    while search_index._working.get(engine) and time.monotonic() < deadline:
        time.sleep(0.01)
    engine.dispose()


def original(client, endpoint, params, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(search_index, "_engine", lambda db: None)
        response = client.get(endpoint, params=params)
        assert response.status_code == 200, response.text
        return response.json()


@pytest.mark.parametrize("kind", ["dil", "prabayar", "pascabayar", "idpel_kosong", "idpel_tidak_ketemu"])
def test_source_search_matches_original_substrings_scope_and_pages(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    identity = "" if kind == "idpel_kosong" else "00123"
    content = (
        "IDPEL,NAMA,KODEGARDU,LAT,LON\n"
        f"{identity},Alice 100%_A\\B,GARDU42,-6.2,106.8\n"
        f"{identity},budi Sample,GARDU43,-6.2,106.8\n"
        f"{identity},Cafe café,GARDU44,-6.2,106.8\n"
    )
    old = upload(client, kind, content)
    upload(client, kind, content)
    endpoint = f"/master/{kind}/records" if kind in {"dil", "prabayar", "pascabayar"} else f"/corrections/{kind}/records"
    before = [(r.id, r.data, r.normalized_data) for r in db_session.query(SourceRecord).all()]
    for q in ("ice", "BUDI", "00123", "%", "_", "A\\B", "fé", "a", "42", "' OR 1=1 --"):
        for scope in ({}, {"batch_id": old}, {"skip": 1, "limit": 1}):
            params = {"q": q, **scope}
            expected = original(client, endpoint, params, monkeypatch)
            actual = client.get(endpoint, params=params)
            assert actual.status_code == 200, actual.text
            assert actual.json() == expected, (q, scope)
    assert [(r.id, r.data, r.normalized_data) for r in db_session.query(SourceRecord).all()] == before
    plan = db_session.connection().exec_driver_sql(
        "EXPLAIN QUERY PLAN SELECT rowid FROM quick_search_v1_source WHERE search_text LIKE '%Alice%'"
    ).all()
    assert any("L0" in row[3] for row in plan), plan


def test_index_follows_edits_rollbacks_inserts_and_deletes(
    client: TestClient, db_session: Session,
) -> None:
    batch = upload(client, "dil", "IDPEL,NAMA,LAT,LON\n001,Original,-6.2,106.8\n")
    endpoint = "/master/dil/records"
    assert client.get(endpoint, params={"q": "Original"}).json()["total"] == 1
    record = db_session.query(SourceRecord).filter_by(batch_id=batch).one()
    record.normalized_data = {**record.normalized_data, "nama": "Renamed"}
    db_session.flush()
    assert client.get(endpoint, params={"q": "Renamed"}).json()["total"] == 1
    db_session.rollback()
    assert client.get(endpoint, params={"q": "Original"}).json()["total"] == 1
    assert client.get(endpoint, params={"q": "Renamed"}).json()["total"] == 0
    record.normalized_data = {**record.normalized_data, "nama": "Committed"}
    db_session.commit()
    assert client.get(endpoint, params={"q": "Committed"}).json()["total"] == 1
    upload(client, "dil", "IDPEL,NAMA,LAT,LON\n002,Inserted,-6.2,106.8\n")
    assert client.get(endpoint, params={"q": "Inserted"}).json()["total"] == 1
    db_session.delete(record)
    db_session.commit()
    assert client.get(endpoint, params={"q": "Committed"}).json()["total"] == 0


def test_background_preparation_is_reported_and_resumes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search_index, "CHUNK_ROWS", 2)
    upload(client, "dil", "IDPEL,NAMA,LAT,LON\n" + "001,Target,-6.2,106.8\n" * 8)
    endpoint = "/master/dil/records"
    first = client.get(endpoint, params={"q": "Target"}).json()
    assert first["search_index"]["ready"] is False
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = client.get(endpoint, params={"q": "Target"}).json()
        if "search_index" not in result:
            break
        time.sleep(0.02)
    assert result["total"] == 8


def test_preparation_bounds_reads_when_generated_master_rows_are_skipped(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = UploadBatch(dataset_type=DatasetType.MASTER, filename="generated")
    db_session.add(batch)
    db_session.flush()
    for index in range(5):
        db_session.add(SourceRecord(batch_id=batch.id, data={}, normalized_data={"nama": "Excluded"}, row_number=index))
    db_session.commit()
    upload(client, "dil", "IDPEL,NAMA,LAT,LON\n001,Included,-6.2,106.8\n")
    monkeypatch.setattr(search_index, "CHUNK_ROWS", 2)
    engine = db_session.get_bind()
    assert search_index._initialize(engine, "source")
    assert search_index._chunk(engine, "source") is False
    with engine.connect() as connection:
        last, processed = connection.exec_driver_sql(
            "SELECT last_id,processed FROM quick_search_progress WHERE kind='quick_search_v1_source'"
        ).one()
        assert (last, processed) == (2, 0)
    assert search_index._chunk(engine, "source") is False
    assert search_index._chunk(engine, "source") is True
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM quick_search_v1_source").scalar_one() == 1
        assert connection.exec_driver_sql(
            "SELECT search_text FROM quick_search_v1_source"
        ).scalar_one().find("Included") >= 0


def test_pdpj_and_saved_result_search_preserve_candidates_actors_and_versions(
    client: TestClient, db_session: Session, partial: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    choice = test_correction_results.choose(client, partial)
    endpoint = partial["base"] + "/results"
    for q in ("Target", "First", "Second", choice["current"]["actor"], "%", "001"):
        params = {"q": q, "status": "all", "generation": 1}
        expected = original(client, endpoint, params, monkeypatch)
        actual = client.get(endpoint, params=params)
        assert actual.status_code == 200, actual.text
        assert actual.json() == expected, q
    endpoint = f"/pdpj/reviews/{partial['pdpj_review_id']}/rows"
    for q in ("001", "PDPJ", "_"):
        expected = original(client, endpoint, {"q": q}, monkeypatch)
        assert client.get(endpoint, params={"q": q}).json() == expected
    row = db_session.query(PdpjRow).filter_by(review_id=partial["pdpj_review_id"]).first()
    row.current_fields = {**row.current_fields, "nama": "Updated PDPJ name"}
    db_session.commit()
    assert client.get(endpoint, params={"q": "Updated PDPJ"}).json()["total"] == 1
    row.current_fields = {
        **row.current_fields, "target_ref": "AGENDA-ONLY",
        "meter_ref": "METER-98765", "nomor_meter_kwh": "KWH-12345",
        "nomor_meter_prepaid": "PRE-44444",
    }
    db_session.commit()
    for term in ("98765", "12345", "44444"):
        assert client.get(endpoint, params={"q": term}).json()["total"] == 1
