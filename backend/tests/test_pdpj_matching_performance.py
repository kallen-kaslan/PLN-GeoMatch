"""Use indexed matches and cached fields without changing recommendations or errors."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.pdpj import PdpjRecommendation
from app.models.upload import SourceRecord, UploadBatch
from app.modules.pdpj import service
from app.modules.upload.normalization import (
    NORMALIZATION_VERSION,
    extract_standard_fields,
)
from tests.test_pdpj_validation import upload


def test_master_lookup_searches_both_index_columns_and_does_not_load_raw_cells(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    master = upload(
        client,
        "dil",
        "IDPEL,NAMA,LAT,LON\n001,Matched,-6.2,106.8\n"
        + "".join(f"{10000 + i},Other,-6.3,106.9\n" for i in range(5000)),
    )
    target = upload(
        client, "pdpj", "IDPEL,NAMA,LAT,LON\n" + "001,Target,-6.2,106.8\n" * 100
    )
    queries = []
    raw_normalization = Mock(wraps=service.extract_standard_fields)
    monkeypatch.setattr(service, "extract_standard_fields", raw_normalization)

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        if (
            statement.lstrip().startswith("SELECT")
            and "source_records.batch_id IN" in statement
            and "source_records.idpel IN" in statement
        ):
            queries.append((statement, parameters))

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        response = client.post(
            "/pdpj/reviews", json={"batch_id": target, "master_batch_ids": [master]}
        )
        assert response.status_code == 200, response.json()
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)
    assert len(queries) == 1
    statement, parameters = queries[0]
    assert "ORDER BY" not in statement
    assert "source_records.data" not in statement
    plan = (
        db_session.connection()
        .exec_driver_sql("EXPLAIN QUERY PLAN " + statement, parameters)
        .all()
    )
    assert any("batch_id=? AND idpel=?" in row[3] for row in plan)
    assert not any("IDPEL" in call.args[0] for call in raw_normalization.call_args_list)
    assert db_session.query(PdpjRecommendation).count() == 100


@pytest.mark.parametrize("cache", ["current", "old", "missing"])
def test_recommendations_keep_original_order_errors_fields_and_provenance(
    client: TestClient, db_session: Session, cache: str
) -> None:
    first = upload(
        client,
        "prabayar",
        "IDPEL,NAMA,LAT,LON,DAYA\n001,First,,,900\n002,Second,-6.2,106.8,1300\n",
    )
    second = upload(
        client,
        "dil",
        "IDPEL,NAMA,KOORDINAT_Y,KOORDINAT_X,DAYA\n001,Invalid,bad,106.8,bad\n001,Third,-6.3,106.9,2200\n",
    )
    batch = db_session.get(UploadBatch, second)
    batch.period = "2026-10"
    if cache == "old":
        batch.catalog_version = NORMALIZATION_VERSION - 1
    if cache == "missing":
        for record in db_session.query(SourceRecord).filter_by(batch_id=second):
            record.normalized_data = None
    db_session.commit()
    expected = []
    for record, source in (
        db_session.query(SourceRecord, UploadBatch)
        .join(UploadBatch)
        .filter(SourceRecord.batch_id.in_([first, second]), SourceRecord.idpel == "001")
        .order_by(UploadBatch.id, SourceRecord.id)
    ):
        fields = extract_standard_fields(record.data, source.column_mapping)
        fields["tglbaca"] = fields["tglbaca"] or source.period
        errors = fields.pop("validation_errors")
        expected.append(
            {
                "fields": fields,
                "validation_errors": errors,
                "source_record_id": record.id,
                "provenance": {
                    "batch_id": source.id,
                    "filename": source.filename,
                    "dataset_type": source.dataset_type.value,
                    "row_number": record.row_number,
                    "source_sheet": source.source_sheet,
                    "period": fields["tglbaca"],
                },
            }
        )
    target = upload(client, "pdpj", "IDPEL,NAMA,LAT,LON\n001,Target,-6.2,106.8\n")
    response = client.post(
        "/pdpj/reviews", json={"batch_id": target, "master_batch_ids": [second, first]}
    )
    assert response.status_code == 200, response.json()
    actual = [
        {
            "fields": item.fields,
            "validation_errors": item.validation_errors,
            "source_record_id": item.source_record_id,
            "provenance": item.provenance,
        }
        for item in db_session.query(PdpjRecommendation).order_by(PdpjRecommendation.id)
    ]
    assert actual == expected
    assert len(actual) == 3
    assert actual[1]["validation_errors"] == [
        {"field": "lat", "code": "koordinat_tidak_valid"},
        {"field": "daya", "code": "daya_tidak_valid"},
    ]
