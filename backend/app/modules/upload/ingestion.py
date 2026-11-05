"""Stream one explicitly selected sheet into a pending, non-reference batch."""

from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.performance import timed

from .progress_state import UPLOAD_PROGRESS
from .reader import IMPORT_CHUNK_ROWS, read_upload


@timed("upload.read_and_store")
def import_raw_sheet(
    db: Session,
    source: BinaryIO,
    filename: str,
    kind: DatasetType,
    sheet_name: str | None,
    period: str | None,
    chunk_rows: int | None = None,
    archive_id: int | None = None,
) -> UploadBatch:
    batch_rows = chunk_rows or IMPORT_CHUNK_ROWS
    with read_upload(source, filename, sheet_name) as (selected_sheet, rows):
        batch = UploadBatch(
            filename=filename,
            dataset_type=kind,
            status=BatchStatus.NEEDS_MAPPING,
            total_rows=0,
            catalog_version=0,
            period=period,
            source_sheet=selected_sheet,
        )
        db.add(batch)
        db.flush()
        initial_progress = {
            "batch_id": batch.id,
            "total_rows": 0,
            "processed_rows": 0,
            "valid_rows": 0,
            "errors": [],
            "status": "uploading",
        }
        UPLOAD_PROGRESS[batch.id] = initial_progress
        if archive_id is not None:
            UPLOAD_PROGRESS[f"archive_{archive_id}"] = initial_progress

        pending = []
        total = 0
        for number, row in rows:
            if total == 0:
                batch.source_headers = list(row)
            pending.append({"batch_id": batch.id, "data": row, "row_number": number})
            total += 1
            if len(pending) >= batch_rows:
                db.bulk_insert_mappings(SourceRecord.__mapper__, pending)
                pending.clear()
                chunk_progress = {
                    "batch_id": batch.id,
                    "total_rows": 0,
                    "processed_rows": total,
                    "valid_rows": total,
                    "errors": [],
                    "status": "uploading",
                }
                UPLOAD_PROGRESS[batch.id] = chunk_progress
                if archive_id is not None:
                    UPLOAD_PROGRESS[f"archive_{archive_id}"] = chunk_progress
        if not total:
            raise ValueError("File kosong atau tidak memiliki baris data.")
        if pending:
            db.bulk_insert_mappings(SourceRecord.__mapper__, pending)
        batch.total_rows = total
        done_progress = {
            "batch_id": batch.id,
            "total_rows": total,
            "processed_rows": total,
            "valid_rows": total,
            "errors": [],
            "status": "uploaded",
        }
        UPLOAD_PROGRESS[batch.id] = done_progress
        if archive_id is not None:
            UPLOAD_PROGRESS[f"archive_{archive_id}"] = done_progress
    return batch
