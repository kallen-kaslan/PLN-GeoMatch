"""Stream one explicitly selected sheet into a pending, non-reference batch."""

from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch

from .reader import IMPORT_CHUNK_ROWS, read_upload


def import_raw_sheet(
    db: Session,
    source: BinaryIO,
    filename: str,
    kind: DatasetType,
    sheet_name: str | None,
    period: str | None,
    chunk_rows: int | None = None,
) -> UploadBatch:
    batch_rows = chunk_rows or IMPORT_CHUNK_ROWS
    with read_upload(source, filename, sheet_name) as (selected_sheet, rows):
        batch = UploadBatch(
            filename=filename,
            dataset_type=kind,
            status=BatchStatus.NEEDS_MAPPING,
            total_rows=0,
            period=period,
            source_sheet=selected_sheet,
        )
        db.add(batch)
        db.flush()
        pending = []
        total = 0
        for number, row in rows:
            pending.append({"batch_id": batch.id, "data": row, "row_number": number})
            total += 1
            if len(pending) >= batch_rows:
                db.bulk_insert_mappings(SourceRecord.__mapper__, pending)
                pending.clear()
        if not total:
            raise ValueError("File kosong atau tidak memiliki baris data.")
        if pending:
            db.bulk_insert_mappings(SourceRecord.__mapper__, pending)
        batch.total_rows = total
    return batch
