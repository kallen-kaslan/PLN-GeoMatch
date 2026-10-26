"""Master catalogue upload, provenance, filtering, DIL integration, and migration."""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.master_schema import upgrade_master_catalog
from app.models.matching import ReconciliationProcess
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.pipeline import execute_pipeline, pin_pipeline_sources


def import_master(
    client: TestClient,
    kind: str,
    content: str,
    mapping: dict[str, str] | None = None,
    filename: str = "source.csv",
    period: str | None = None,
) -> int:
    data = {"dataset_type": kind}
    if period:
        data["period"] = period
    uploaded = client.post(
        "/upload/", data=data, files={"file": (filename, content.encode(), "text/csv")}
    )
    assert uploaded.status_code == 200
    batch_id = uploaded.json()["id"]
    checked = client.post(
        "/upload/confirm-mapping",
        json={"batch_id": batch_id, "column_mapping": mapping or {"idpel": "IDPEL"}},
    )
    assert checked.status_code == 200
    return batch_id


@pytest.mark.parametrize("kind", ["prabayar", "pascabayar", "dil"])
def test_import_master_and_read_saved_source_metadata(
    client: TestClient, kind: str
) -> None:
    mapping = {
        "idpel": "CUSTOMER",
        "nama": "CUSTOM_NAME",
        "kode_dil": "SOURCE_CODE",
        "kode_gardu": "GARDU",
    }
    batch_id = import_master(
        client,
        kind,
        "CUSTOMER,CUSTOM_NAME,SOURCE_CODE,GARDU\n001234567890,Budi,DL-17,G-03\n",
        mapping,
        "customers.csv",
        "2026-10",
    )
    files = client.get(f"/master/{kind}/batches").json()
    assert len(files) == 1 and files[0]["id"] == batch_id
    assert files[0]["period"] == "2026-10"
    preview = client.get(f"/master/{kind}/batches/{batch_id}").json()
    assert preview["headers"] == ["CUSTOMER", "CUSTOM_NAME", "SOURCE_CODE", "GARDU"]
    assert preview["column_mapping"] == mapping
    records = client.get(f"/master/{kind}/records").json()
    assert records["total"] == 1
    row = records["items"][0]
    assert row["row_number"] == 2 and row["period"] == "2026-10"
    assert row["fields"]["idpel"] == "001234567890"
    assert (
        row["fields"]["kode_dil"] == "DL-17" and row["fields"]["kode_gardu"] == "G-03"
    )
    assert row["is_valid"] and not row["coordinates_complete"]
    detail = client.get(f"/master/{kind}/records/{row['id']}").json()
    assert detail["raw_data"]["CUSTOMER"] == "001234567890"
    assert detail["filename"] == "customers.csv" and detail["row_number"] == 2
    assert detail["column_mapping"] == mapping


def test_master_summary_filters_and_pagination_keep_observations(
    client: TestClient,
) -> None:
    source = "IDPEL,NAMA,LAT,LON\n001,Budi,-6.2,106.8\n001,Budi,,\n002,Siti,bad,106.8\n003,Agus,-6.21,106.81\n"
    batch_id = import_master(client, "dil", source)
    summary = client.get("/master/dil/summary").json()
    assert summary["total_rows"] == 4 and summary["valid_rows"] == 3
    assert summary["invalid_rows"] == 1 and summary["incomplete_coordinates"] == 1
    assert summary["unique_idpels"] == 2 and summary["duplicate_observations"] == 1
    page = client.get("/master/dil/records?limit=2&skip=2").json()
    assert page["total"] == 4 and len(page["items"]) == 2
    assert page["items"][0]["row_number"] == 4
    assert client.get("/master/dil/records?status=incomplete").json()["total"] == 1
    assert client.get("/master/dil/records?status=valid").json()["total"] == 3
    assert (
        client.get("/master/dil/records?status=invalid").json()["items"][0]["fields"][
            "idpel"
        ]
        == "002"
    )
    assert client.get("/master/dil/records?q=budi").json()["total"] == 2
    assert client.get("/master/dil/records?q=003").json()["total"] == 1
    assert client.get("/master/dil/records?q=%25").json()["total"] == 0
    assert (
        client.get(f"/master/dil/summary?batch_id={batch_id}").json()["total_rows"] == 4
    )


def test_catalogue_cannot_mix_master_types_or_target_batches(
    client: TestClient,
) -> None:
    prepaid = import_master(client, "prabayar", "IDPEL\n001\n")
    postpaid = import_master(client, "pascabayar", "IDPEL\n002\n")
    assert len(client.get("/master/prabayar/batches").json()) == 1
    record_id = client.get("/master/prabayar/records").json()["items"][0]["id"]
    assert client.get(f"/master/dil/records/{record_id}").status_code == 404
    assert client.get(f"/master/prabayar/batches/{postpaid}").status_code == 404
    assert client.get(f"/master/dil/records?batch_id={prepaid}").status_code == 404
    assert client.get("/master/dil/batches/9999").status_code == 404
    assert client.get("/master/dil/records/9999").status_code == 404
    assert client.get("/master/target/records").status_code == 422
    assert client.get("/master/dil/records?limit=10000").status_code == 422


def test_pending_upload_can_resume_mapping_without_entering_reference(
    client: TestClient,
) -> None:
    uploaded = client.post(
        "/upload/",
        data={"dataset_type": "dil"},
        files={"file": ("pending.csv", b"C\n001\n", "text/csv")},
    )
    batch_id = uploaded.json()["id"]
    metadata = client.get(f"/master/dil/batches/{batch_id}").json()
    assert metadata["headers"] == ["C"] and metadata["preview"] == [{"C": "001"}]
    assert metadata["status"] == "needs_mapping"
    summary = client.get("/master/dil/summary").json()
    assert summary["total_rows"] == 0 and summary["pending_files"] == 1
    assert client.get(f"/master/dil/records?batch_id={batch_id}").json()["items"] == []
    assert (
        client.post(
            "/upload/confirm-mapping",
            json={"batch_id": batch_id, "column_mapping": {"idpel": "C"}},
        ).status_code
        == 200
    )
    assert client.get("/master/dil/records").json()["total"] == 1


def test_selected_excel_sheet_and_row_period_override_are_preserved(
    client: TestClient,
) -> None:
    book = Workbook()
    book.active.title = "Petunjuk"
    book.active.append(["Jangan impor sheet ini"])
    sheet = book.create_sheet("Data DIL")
    sheet.append(["IDPEL", "PERIODE", "KODE"])
    sheet.append(["000123456789", "2026-09", "CODE-1"])
    sheet.append(["000123456790", "", "CODE-2"])
    content = io.BytesIO()
    book.save(content)
    response = client.post(
        "/upload/",
        data={"dataset_type": "dil", "period": "2026-10", "sheet_name": "Data DIL"},
        files={
            "file": (
                "dil.xlsx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    batch_id = response.json()["id"]
    assert (
        client.post(
            "/upload/confirm-mapping",
            json={
                "batch_id": batch_id,
                "column_mapping": {"idpel": "IDPEL", "kode_dil": "KODE"},
            },
        ).status_code
        == 200
    )
    rows = client.get("/master/dil/records").json()["items"]
    assert [row["period"] for row in rows] == ["2026-09", "2026-10"]
    assert (
        rows[0]["source_sheet"] == "Data DIL"
        and rows[0]["fields"]["idpel"] == "000123456789"
    )
    assert rows[1]["row_number"] == 3


def test_file_filter_keeps_summary_separate_from_table_page(client: TestClient) -> None:
    first = import_master(client, "prabayar", "IDPEL\n001\n002\n", filename="first.csv")
    import_master(client, "prabayar", "IDPEL\n003\n", filename="second.csv")
    assert client.get("/master/prabayar/summary").json()["total_rows"] == 3
    assert (
        client.get(f"/master/prabayar/summary?batch_id={first}").json()["total_rows"]
        == 2
    )
    rows = client.get(f"/master/prabayar/records?batch_id={first}&limit=1").json()
    assert rows["total"] == 2 and len(rows["items"]) == 1
    assert rows["items"][0]["filename"] == "first.csv"


def test_dil_supplements_missing_fields_without_replacing_known_location(
    client: TestClient, db_session: Session
) -> None:
    prepaid = import_master(
        client, "prabayar", "IDPEL,LAT,LON,NAMA\n001,-6.2,106.8,Asli\n002,,,\n"
    )
    dil = import_master(
        client,
        "dil",
        "IDPEL,LAT,LON,NAMA,KODE_DIL,KODE_GARDU\n001,-7,110,DIL,DL1,G1\n002,-6.3,106.9,Lengkap,DL2,G2\n003,,,Hanya DIL,DL3,G3\n",
    )
    result = build_combined_master(db_session, [], [prepaid], [dil])
    rows = {
        record.idpel: record.data
        for record in db_session.query(SourceRecord)
        .filter(SourceRecord.batch_id == result["master_batch_id"])
        .all()
    }
    assert result["total_dil_raw"] == 3 and result["total_master_clean"] == 3
    assert rows["001"]["lat"] == -6.2 and rows["001"]["nama"] == "Asli"
    assert rows["001"]["kode_dil"] == "DL1" and rows["001"]["kode_gardu"] == "G1"
    assert rows["001"]["jenis_pel"] == "PRABAYAR"
    assert rows["002"]["lat"] == -6.3 and rows["002"]["lon"] == 106.9
    assert rows["003"]["lat"] is None and rows["003"]["jenis_pel"] is None
    assert len(rows["001"]["source_observations"]) == 2
    assert rows["001"]["source_observations"][1]["fields"]["lat"] == -7
    assert rows["001"]["source_observations"][1]["dataset_type"] == "dil"


def test_pipeline_accepts_dil_as_the_only_reference_source(
    client: TestClient, db_session: Session
) -> None:
    dil = import_master(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    sources = pin_pipeline_sources(db_session, None, None, None, None)
    assert sources["dil"] == [dil]
    process = ReconciliationProcess(
        process_name="DIL reference", radius_meters=100, source_batches=sources
    )
    db_session.add(process)
    db_session.commit()
    result = execute_pipeline(db_session, process.id)
    assert result["status"] == "completed" and result["master_snapshot_id"] is not None


def test_catalog_upgrade_backfills_only_derived_metadata(db_session: Session) -> None:
    raw = {"CUSTOMER": "000123", "NAME": "Sumber"}
    batch = UploadBatch(
        filename="legacy.csv",
        dataset_type=DatasetType.DIL,
        status=BatchStatus.COMPLETED,
        column_mapping={"idpel": "CUSTOMER", "nama": "NAME"},
        period="2026-10",
    )
    db_session.add(batch)
    db_session.flush()
    record = SourceRecord(batch_id=batch.id, data=raw)
    db_session.add(record)
    db_session.commit()
    with db_session.get_bind().begin() as connection:
        upgrade_master_catalog(connection)
        upgrade_master_catalog(connection)
    db_session.refresh(record)
    assert record.data == raw and record.row_number == 2
    assert record.normalized_data["idpel"] == "000123"
    assert record.normalized_data["tglbaca"] == "2026-10"
    assert record.is_valid


def test_dil_latest_observation_is_selected_while_sources_are_retained(
    client: TestClient, db_session: Session
) -> None:
    first = import_master(client, "dil", "IDPEL,NAMA\n001,Lama\n", period="2026-09")
    second = import_master(client, "dil", "IDPEL,NAMA\n001,Baru\n", period="2026-10")
    combined = build_combined_master(db_session, [], [], [first, second])
    record = (
        db_session.query(SourceRecord)
        .filter(SourceRecord.batch_id == combined["master_batch_id"])
        .one()
    )
    assert (
        record.data["nama"] == "Baru" and len(record.data["source_observations"]) == 2
    )


@pytest.mark.parametrize("separator", [",", ";", "\t"])
def test_actual_dil_headers_keep_codes_meters_and_blank_columns_separate(
    client: TestClient, separator: str
) -> None:
    headers = [
        "NO",
        "V_BULAN_REKAP",
        "",
        "IDPEL",
        "UNITUPI",
        "UNITAP",
        "UNITUP",
        "NAMA",
        "NAMAPNJ",
        "NOBANG",
        "KETNOBANG",
        "RT",
        "RW",
        "JENISLAYANAN",
        "KODEDLPD",
        "KDDK",
        "NOMOR_METER_KWH",
        "NOMOR_METER_PREPAID",
        "NOMOR_GARDU",
        "NAMA_GARDU",
        "NAMA_PENYULANG",
        "KOORDINAT_X",
        "KOORDINAT_Y",
        "STATUS_DIL",
        "KETERANGAN_3T",
        "NAMA",
    ]
    values = [
        "99",
        "202610",
        "separator retained",
        "000123456789",
        "01",
        "02",
        "03",
        "Pelanggan",
        "Jalan Contoh",
        "007",
        "A",
        "01",
        "02",
        "PRABAYAR",
        "DLP-01",
        "0007",
        "000123",
        "000456",
        "G-001",
        "Gardu Satu",
        "Penyulang Satu",
        "106.8",
        "-6.2",
        "AKTIF",
        "catatan asli",
        "nilai kolom kedua",
    ]
    batch_id = import_master(
        client, "dil", separator.join(headers) + "\n" + separator.join(values) + "\n"
    )
    preview = client.get(f"/master/dil/batches/{batch_id}").json()
    assert preview["headers"][2] == "Kolom_3" and preview["headers"][-1] == "NAMA__2"
    row = client.get("/master/dil/records").json()["items"][0]
    fields = row["fields"]
    assert row["row_number"] == 2 and row["period"] == "202610"
    assert fields["kode_dil"] is None
    assert fields["kode_dlpd"] == "DLP-01" and fields["kddk"] == "0007"
    assert fields["kode_gardu"] == "G-001" and fields["status_dil"] == "AKTIF"
    assert fields["nomor_meter_kwh"] == "000123"
    assert fields["nomor_meter_prepaid"] == "000456"
    assert fields["target_ref"] == "000123"
    assert fields["unit_upi"] == "01" and fields["unit_ap"] == "02"
    assert fields["nama_pnj"] == "Jalan Contoh" and fields["no_bang"] == "007"
    assert fields["lat"] == -6.2 and fields["lon"] == 106.8
    assert row["is_valid"] and row["coordinates_complete"]
    detail = client.get(f"/master/dil/records/{row['id']}").json()
    assert detail["raw_data"]["Kolom_3"] == "separator retained"
    assert detail["raw_data"]["KETERANGAN_3T"] == "catatan asli"
    assert detail["raw_data"]["NAMA__2"] == "nilai kolom kedua"
    assert client.get("/master/dil/records?q=DLP-01").json()["total"] == 1
    assert client.get("/master/dil/records?q=000456").json()["total"] == 1


def test_catalog_upgrade_refreshes_stale_extraction_without_changing_raw_cells(
    db_session: Session,
) -> None:
    batch = UploadBatch(
        filename="old-dil.csv",
        dataset_type=DatasetType.DIL,
        status=BatchStatus.COMPLETED,
    )
    db_session.add(batch)
    db_session.flush()
    raw = {"IDPEL": "000123", "V_BULAN_REKAP": "202610", "NOMOR_GARDU": "G-01"}
    record = SourceRecord(
        batch_id=batch.id,
        data=raw,
        row_number=2,
        normalized_data={"idpel": "000123", "_normalization_version": 1},
    )
    db_session.add(record)
    db_session.commit()
    with db_session.get_bind().begin() as connection:
        upgrade_master_catalog(connection)
    db_session.refresh(record)
    assert record.data == raw
    assert record.normalized_data["kode_gardu"] == "G-01"
    assert record.normalized_data["tglbaca"] == "202610"


def test_latest_dil_period_compares_compact_month_with_file_period(
    client: TestClient,
    db_session: Session,
) -> None:
    older = import_master(client, "dil", "IDPEL,V_BULAN_REKAP,NAMA\n001,202609,Lama\n")
    newer = import_master(client, "dil", "IDPEL,NAMA\n001,Baru\n", period="2026-10")
    combined = build_combined_master(db_session, [], [], [newer, older])
    record = (
        db_session.query(SourceRecord)
        .filter(SourceRecord.batch_id == combined["master_batch_id"])
        .one()
    )
    assert record.data["nama"] == "Baru"
    assert len(record.data["source_observations"]) == 2


def test_dil_supplement_uses_latest_source_without_erasing_known_coordinates(
    client: TestClient,
    db_session: Session,
) -> None:
    prepaid = import_master(client, "prabayar", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    older = import_master(
        client, "dil", "IDPEL,V_BULAN_REKAP,NOMOR_GARDU\n001,202609,G-OLD\n"
    )
    newer = import_master(
        client,
        "dil",
        "IDPEL,V_BULAN_REKAP,NOMOR_GARDU,LAT,LON\n001,202610,G-NEW,-7,110\n",
    )
    combined = build_combined_master(db_session, [], [prepaid], [older, newer])
    record = (
        db_session.query(SourceRecord)
        .filter(SourceRecord.batch_id == combined["master_batch_id"])
        .one()
    )
    assert record.data["kode_gardu"] == "G-NEW"
    assert record.data["lat"] == -6.2 and record.data["lon"] == 106.8
    assert record.data["jenis_pel"] == "PRABAYAR"
    assert len(record.data["source_observations"]) == 3
