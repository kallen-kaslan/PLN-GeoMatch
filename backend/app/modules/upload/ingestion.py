"""Stream one explicitly selected sheet into a pending, non-reference batch."""

from collections.abc import Callable
from typing import BinaryIO

from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.performance import timed
from sqlalchemy.orm import Session

from .progress import UploadProgress
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
    progress: UploadProgress | None = None,
    on_batch: Callable[[UploadBatch], None] | None = None,
    existing_batch: UploadBatch | None = None,
) -> UploadBatch:
    batch_rows = chunk_rows or IMPORT_CHUNK_ROWS
    if progress:
        progress.stage("reading")
    with read_upload(source, filename, sheet_name) as (selected_sheet, rows):
        batch = existing_batch or UploadBatch(
            filename=filename,
            dataset_type=kind,
            status=BatchStatus.PROCESSING,
            total_rows=0,
            catalog_version=0,
            period=period,
            source_sheet=selected_sheet,
        )
        batch.status = BatchStatus.PROCESSING
        db.add(batch)
        db.flush()
        if progress:
            progress.batch_id = batch.id
        if on_batch and existing_batch is None:
            on_batch(batch)
        pending = []
        total = batch.total_rows or 0
        # A failed request may have committed an earlier pause checkpoint.
        skip = total
        for number, row in rows:
            if skip:
                skip -= 1
                continue
            if total == 0:
                batch.source_headers = list(row)
            pending.append({"batch_id": batch.id, "data": row, "row_number": number})
            total += 1
            if len(pending) >= batch_rows:
                db.bulk_insert_mappings(SourceRecord.__mapper__, pending)
                pending.clear()
                batch.total_rows = total
                if progress:
                    progress.update(total)
                    progress.checkpoint(db)
        if skip:
            raise ValueError(
                "Isi berkas tidak sesuai dengan checkpoint impor. Unggah kembali berkas sumber."
            )
        if not total:
            raise ValueError("File kosong atau tidak memiliki baris data.")
        if pending:
            db.bulk_insert_mappings(SourceRecord.__mapper__, pending)
        batch.total_rows = total
        batch.status = BatchStatus.NEEDS_MAPPING
        if progress:
            progress.update(total, total)
    return batch
