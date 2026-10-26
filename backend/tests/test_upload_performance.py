"""Regression: mapped fields reach the master without altering raw source cells."""

from sqlalchemy.orm import Session

from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.spatial.master_builder import build_combined_master


def test_mapping_persistence_and_extraction(db_session: Session) -> None:
    raw_data = {
        "CUSTOMER": "005300000001",
        "CUSTOM_NAME": "BUDI CUSTOM",
        "CUSTOM_Y": -6.2,
        "CUSTOM_X": 106.8,
        "CUSTOM_TARIFF": "R1",
        "CUSTOM_POWER": "900",
        "TGL_BACA": "2023-10-01",
    }
    batch = UploadBatch(
        filename="custom_cols.csv",
        dataset_type=DatasetType.PASCABAYAR,
        status=BatchStatus.COMPLETED,
        column_mapping={
            "idpel": "CUSTOMER",
            "nama": "CUSTOM_NAME",
            "latitude": "CUSTOM_Y",
            "longitude": "CUSTOM_X",
            "tarif": "CUSTOM_TARIFF",
            "daya": "CUSTOM_POWER",
        },
    )
    db_session.add(batch)
    db_session.flush()
    source = SourceRecord(batch_id=batch.id, data=raw_data)
    db_session.add(source)
    db_session.commit()
    result = build_combined_master(db_session, [batch.id], [])
    master = (
        db_session.query(SourceRecord)
        .filter(SourceRecord.batch_id == result["master_batch_id"])
        .one()
    )
    assert master.idpel == "005300000001"
    assert master.data["latitude"] == -6.2
    assert master.data["longitude"] == 106.8
    assert master.data["tarif"] == "R1"
    assert master.data["daya"] == 900
    assert master.data["source_record_id"] == source.id
    db_session.refresh(source)
    assert source.data == raw_data
