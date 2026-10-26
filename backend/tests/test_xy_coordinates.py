"""Regressions for PLN exports using X=latitude and Y=longitude."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.coordinate_schema import repair_xy_coordinates
from app.models.coordinate_repair import CoordinateRepair
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.upload.normalization import extract_standard_fields


@pytest.mark.parametrize(
    "headers",
    [("KOORDINAT_X", "KOORDINAT_Y"), ("Koordinat X", "Koordinat Y"), ("X", "Y")],
)
@pytest.mark.parametrize(
    "mapping", [None, {"lat": "KOORDINAT_Y", "lon": "KOORDINAT_X"}]
)
def test_reverse_xy_pair_is_recovered_without_changing_raw(
    headers: tuple[str, str], mapping: dict | None
) -> None:
    x, y = headers
    raw = {"IDPEL": "001", x: "-6,78792521", y: "108,57478594"}
    selected = {"lat": y, "lon": x} if mapping else None
    fields = extract_standard_fields(raw, selected)
    assert fields["lat"] == -6.78792521 and fields["lon"] == 108.57478594
    assert fields["validation_errors"] == []
    assert fields["_coordinate_axes_swapped"]
    assert raw[x] == "-6,78792521" and raw[y] == "108,57478594"


@pytest.mark.parametrize(
    "raw,mapping,expected",
    [
        ({"KOORDINAT_X": "106.8", "KOORDINAT_Y": "-6.2"}, None, (-6.2, 106.8)),
        (
            {"KOORDINAT_X": "-6.2", "KOORDINAT_Y": "108.5"},
            {"lat": "KOORDINAT_X", "lon": "KOORDINAT_Y"},
            (-6.2, 108.5),
        ),
        ({"LAT": "108.5", "LON": "-6.2"}, None, (None, -6.2)),
        ({"latitudey": "108.5", "longitudex": "-6.2"}, None, (None, -6.2)),
        ({"KOORDINAT_X": "-6.2", "KOORDINAT_Y": "200"}, None, (None, -6.2)),
        ({"X": "-6.2", "Y": "NaN"}, None, (None, -6.2)),
        ({"X": "-6.2", "Y": ""}, {"lat": "Y", "lon": "X"}, (None, -6.2)),
        ({"X": "31.5", "Y": "74.2"}, None, (74.2, 31.5)),
    ],
)
def test_certain_xy_corrections_do_not_override_named_or_ambiguous_coordinates(
    raw: dict, mapping: dict | None, expected: tuple
) -> None:
    fields = extract_standard_fields(raw, mapping)
    assert (fields["lat"], fields["lon"]) == expected
    assert not fields.get("_coordinate_axes_swapped")


def test_csv_import_xy_mapping_retains_longitude_y_in_reference(
    client: TestClient,
) -> None:
    uploaded = client.post(
        "/upload/",
        data={"dataset_type": "dil"},
        files={
            "file": (
                "xy.csv",
                b"IDPEL,KOORDINAT_X,KOORDINAT_Y\n001,-6.2,108.5\n",
                "text/csv",
            )
        },
    )
    assert uploaded.status_code == 200
    confirmed = client.post(
        "/upload/confirm-mapping",
        json={
            "batch_id": uploaded.json()["id"],
            "column_mapping": {
                "idpel": "IDPEL",
                "lat": "KOORDINAT_Y",
                "lon": "KOORDINAT_X",
            },
        },
    )
    assert confirmed.status_code == 200 and confirmed.json()["error_rows"] == 0
    row = client.get("/master/dil/records").json()["items"][0]
    assert row["fields"]["lat"] == -6.2 and row["fields"]["lon"] == 108.5
    assert row["is_valid"] and row["coordinates_complete"]


def test_existing_source_repair_is_chunked_idempotent_and_keeps_raw_and_pending_data(
    db_session: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import coordinate_schema

    monkeypatch.setattr(coordinate_schema, "REPAIR_CHUNK_ROWS", 1)
    completed = UploadBatch(
        filename="old.csv",
        dataset_type=DatasetType.DIL,
        status=BatchStatus.COMPLETED,
        total_rows=3,
        valid_rows=1,
        error_rows=2,
        column_mapping={"idpel": "IDPEL", "lat": "KOORDINAT_Y", "lon": "KOORDINAT_X"},
    )
    pending = UploadBatch(
        filename="pending.csv",
        dataset_type=DatasetType.DIL,
        status=BatchStatus.NEEDS_MAPPING,
    )
    db_session.add_all([completed, pending])
    db_session.flush()
    raws = [
        {"IDPEL": "001", "KOORDINAT_X": "-6.2", "KOORDINAT_Y": "108.5"},
        {"IDPEL": "002", "KOORDINAT_X": "bad", "KOORDINAT_Y": "108.5"},
        {"IDPEL": "003", "KOORDINAT_X": "", "KOORDINAT_Y": ""},
    ]
    for raw in raws:
        db_session.add(
            SourceRecord(
                batch_id=completed.id,
                data=raw,
                row_number=2,
                idpel=raw["IDPEL"],
                normalized_data={"lat": None, "lon": -6.2, "_normalization_version": 3},
                is_valid=raw["IDPEL"] == "003",
                validation_errors=[]
                if raw["IDPEL"] == "003"
                else [{"field": "lat", "code": "koordinat_tidak_valid"}],
            )
        )
    db_session.add(
        SourceRecord(batch_id=pending.id, data=raws[0], normalized_data=None)
    )
    db_session.commit()
    with db_session.get_bind().begin() as connection:
        result = repair_xy_coordinates(connection)
    assert result == {completed.id: 1}
    db_session.expire_all()
    assert db_session.get(UploadBatch, completed.id).valid_rows == 2
    assert db_session.get(UploadBatch, completed.id).error_rows == 1
    rows = (
        db_session.query(SourceRecord)
        .filter_by(batch_id=completed.id)
        .order_by(SourceRecord.id)
        .all()
    )
    assert [row.data for row in rows] == raws
    assert (
        rows[0].normalized_data["lat"] == -6.2
        and rows[0].normalized_data["lon"] == 108.5
    )
    assert rows[1].is_valid is False and rows[1].normalized_data["lat"] is None
    assert (
        db_session.query(SourceRecord)
        .filter_by(batch_id=pending.id)
        .one()
        .normalized_data
        is None
    )
    with db_session.get_bind().begin() as connection:
        assert repair_xy_coordinates(connection) == {}
    assert db_session.query(CoordinateRepair).count() == 1
    assert client.post("/upload/reset").status_code == 200
