"""Retain original files; previewing an archived sheet never creates reference data."""

import hashlib
import os
import re
from itertools import islice
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4
from zipfile import BadZipFile

from app.config import settings
from app.database import get_db
from app.models.upload import BatchStatus, DatasetType, UploadBatch
from app.models.upload_file import UploadFileArchive, UploadSheetImport
from app.modules.auth.security import CurrentUser
from app.modules.pdpj.service import lock_review_session
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .ingestion import import_raw_sheet
from .progress import UploadProgress, report_progress, track_upload
from .reader import check_file_size, read_upload
from .storage import database_write_error

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


def archive_path(key: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", key):
        raise ValueError("Kunci penyimpanan berkas tidak valid")
    root = Path(settings.UPLOAD_STORAGE_DIR).resolve()
    target = (root / key).resolve()
    if target.parent != root:
        raise ValueError("Lokasi berkas tidak valid")
    return target


def get_archive(db: Session, file_id: int) -> UploadFileArchive:
    archive = db.get(UploadFileArchive, file_id)
    if archive is None:
        raise HTTPException(404, "Berkas dalam riwayat tidak ditemukan")
    return archive


def archive_info(db: Session, archive: UploadFileArchive) -> dict[str, Any]:
    imports = (
        db.query(UploadSheetImport, UploadBatch)
        .join(UploadBatch, UploadBatch.id == UploadSheetImport.batch_id)
        .filter(UploadSheetImport.file_id == archive.id)
        .order_by(UploadBatch.id)
        .all()
    )
    return {
        "id": archive.id,
        "filename": archive.filename,
        "size_bytes": archive.size_bytes,
        "sheet_names": archive.sheet_names,
        "created_at": archive.created_at,
        "imports": [
            {
                "batch_id": batch.id,
                "dataset_type": batch.dataset_type,
                "source_sheet": batch.source_sheet,
                "period": batch.period,
                "status": batch.status,
                "total_rows": batch.total_rows,
            }
            for _, batch in imports
        ],
    }


@router.get("/files")
def list_files(db: DbSession) -> list[dict[str, Any]]:
    return [
        archive_info(db, item)
        for item in db.query(UploadFileArchive)
        .order_by(UploadFileArchive.id.desc())
        .all()
    ]


@router.post("/files")
@report_progress
def store_file(
    file: Annotated[UploadFile, File()],
    db: DbSession,
    progress: Annotated[UploadProgress, Depends(track_upload)],
) -> dict[str, Any]:
    key = uuid4().hex
    path = archive_path(key)
    committed = False
    created = False
    try:
        filename = file.filename or ""
        if not filename.lower().endswith((".xlsx", ".csv")):
            raise ValueError("Gunakan berkas CSV atau XLSX")
        check_file_size(file.file)
        file.file.seek(0, 2)
        progress.stage("inspecting", file.file.tell(), "bytes")
        progress.checkpoint()
        file.file.seek(0)
        names: list[str] = []
        if filename.lower().endswith(".xlsx"):
            book = load_workbook(file.file, read_only=True, data_only=True)
            try:
                names = book.sheetnames
                if not names:
                    raise ValueError("Berkas Excel tidak memiliki sheet")
            finally:
                book.close()
        file.file.seek(0)
        progress.stage("archiving", progress.snapshot.get("total"), "bytes")
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with path.open("xb") as destination:
            created = True
            while chunk := file.file.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                destination.write(chunk)
                progress.update(size)
                progress.checkpoint()
        progress.stage("registering")
        progress.checkpoint()
        existing = (
            db.query(UploadFileArchive).filter_by(sha256=digest.hexdigest()).first()
        )
        if existing:
            original = archive_path(existing.storage_key)
            if not original.exists():
                os.replace(path, original)
            else:
                path.unlink()
            return archive_info(db, existing)
        archive = UploadFileArchive(
            filename=filename,
            sha256=digest.hexdigest(),
            storage_key=key,
            size_bytes=size,
            sheet_names=names,
        )
        db.add(archive)
        try:
            db.commit()
            committed = True
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(UploadFileArchive).filter_by(sha256=digest.hexdigest()).first()
            )
            if existing is None:
                raise
            path.unlink(missing_ok=True)
            return archive_info(db, existing)
        return archive_info(db, archive)
    except SQLAlchemyError as exc:
        if created and not committed:
            path.unlink(missing_ok=True)
        raise database_write_error(db, exc, "riwayat berkas") from exc
    except (OSError, ValueError, ImportError, BadZipFile) as exc:
        if created and not committed:
            path.unlink(missing_ok=True)
        raise HTTPException(400, f"Berkas tidak dapat disimpan: {exc!s}") from exc
    finally:
        file.file.close()


class SheetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_type: DatasetType
    sheet_name: str | None = Field(None, max_length=128)
    period: str | None = Field(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


def selected_sheet(archive: UploadFileArchive, name: str | None) -> str | None:
    if not archive.sheet_names:
        if name is not None:
            raise HTTPException(422, "Berkas CSV tidak memiliki sheet")
        return None
    if name not in archive.sheet_names:
        raise HTTPException(422, "Pilih sheet yang tersedia dalam riwayat berkas")
    return name


@router.get("/files/{file_id}/preview")
def preview_sheet(
    file_id: int, db: DbSession, sheet_name: str | None = Query(None, max_length=128)
) -> dict[str, Any]:
    archive = get_archive(db, file_id)
    name = selected_sheet(archive, sheet_name)
    path = archive_path(archive.storage_key)
    if not path.is_file():
        raise HTTPException(
            410,
            "Berkas asli tidak tersedia. Unggah kembali berkas yang sama untuk memulihkannya.",
        )
    try:
        with (
            path.open("rb") as source,
            read_upload(source, archive.filename, name) as (sheet, rows),
        ):
            preview = list(islice(rows, 5))
            if not preview:
                raise ValueError("Sheet tidak memiliki baris data setelah nama kolom")
            return {
                "headers": list(preview[0][1]),
                "rows": [row for _, row in preview],
                "headerRow": preview[0][0] - 1,
                "source_sheet": sheet,
            }
    except (OSError, ValueError, ImportError, BadZipFile) as exc:
        raise HTTPException(400, f"Pratinjau tidak dapat dibaca: {exc!s}") from exc


@router.delete("/files/{file_id}")
def delete_file(file_id: int, db: DbSession, user: CurrentUser) -> dict[str, str]:
    if getattr(user.role, "value", user.role) != "admin":
        raise HTTPException(403, "Hanya admin yang dapat menghapus berkas")
    archive = get_archive(db, file_id)
    lock_review_session(db)
    imports = db.query(UploadSheetImport).filter_by(file_id=file_id).all()
    batch_ids = [imp.batch_id for imp in imports]
    if batch_ids:
        from app.models.pdpj import PdpjReview
        from app.models.matching import ReconciliationProcess
        from app.models.master_sisa import MasterSnapshot, MasterPreparation

        has_pdpj = db.query(PdpjReview).filter(PdpjReview.batch_id.in_(batch_ids)).first()
        has_recon = db.query(ReconciliationProcess).filter(ReconciliationProcess.target_batch_id.in_(batch_ids)).first()
        has_snap = db.query(MasterSnapshot).filter(
            (MasterSnapshot.master_batch_id.in_(batch_ids)) | (MasterSnapshot.pdpj_batch_id.in_(batch_ids))
        ).first()
        has_prep = db.query(MasterPreparation).filter(MasterPreparation.master_batch_id.in_(batch_ids)).first()
        if has_pdpj or has_recon or has_snap or has_prep:
            raise HTTPException(409, "Berkas tidak dapat dihapus karena salah satu sheet telah digunakan dalam proses PDPJ, rekonsiliasi, atau snapshot master.")

        from app.models.coordinate_repair import CoordinateRepair
        from app.models.master_sisa import CleanedMasterRecord
        from app.models.upload import SourceRecord

        db.query(CoordinateRepair).filter(CoordinateRepair.batch_id.in_(batch_ids)).delete(synchronize_session=False)
        db.query(CleanedMasterRecord).filter(CleanedMasterRecord.batch_id.in_(batch_ids)).delete(synchronize_session=False)
        db.query(SourceRecord).filter(SourceRecord.batch_id.in_(batch_ids)).delete(synchronize_session=False)
        db.query(UploadSheetImport).filter_by(file_id=file_id).delete(synchronize_session=False)
        db.query(UploadBatch).filter(UploadBatch.id.in_(batch_ids)).delete(synchronize_session=False)
    else:
        db.query(UploadSheetImport).filter_by(file_id=file_id).delete(synchronize_session=False)
    db.delete(archive)
    db.commit()
    try:
        archive_path(archive.storage_key).unlink(missing_ok=True)
    except OSError:
        pass
    return {"message": "Berkas dan sheet terkait berhasil dihapus"}


@router.delete("/files/{file_id}/sheet/{sheet_key}")
def delete_sheet(file_id: int, sheet_key: str, db: DbSession, user: CurrentUser, period: str | None = Query(None), dataset_type: str | None = Query(None)) -> dict[str, str]:
    if getattr(user.role, "value", user.role) != "admin":
        raise HTTPException(403, "Hanya admin yang dapat menghapus sheet")
    get_archive(db, file_id)
    lock_review_session(db)
    sheet_import = db.query(UploadSheetImport).filter_by(
        file_id=file_id,
        sheet_key=sheet_key,
        period_key=period or "",
        dataset_type=dataset_type or ""
    ).first()
    if not sheet_import:
        raise HTTPException(404, "Sheet import tidak ditemukan")
    batch_id = sheet_import.batch_id

    from app.models.pdpj import PdpjReview
    from app.models.matching import ReconciliationProcess
    from app.models.master_sisa import MasterSnapshot, MasterPreparation

    has_pdpj = db.query(PdpjReview).filter(PdpjReview.batch_id == batch_id).first()
    has_recon = db.query(ReconciliationProcess).filter(ReconciliationProcess.target_batch_id == batch_id).first()
    has_snap = db.query(MasterSnapshot).filter(
        (MasterSnapshot.master_batch_id == batch_id) | (MasterSnapshot.pdpj_batch_id == batch_id)
    ).first()
    has_prep = db.query(MasterPreparation).filter(MasterPreparation.master_batch_id == batch_id).first()
    if has_pdpj or has_recon or has_snap or has_prep:
        raise HTTPException(409, "Sheet tidak dapat dihapus karena telah digunakan dalam proses PDPJ, rekonsiliasi, atau snapshot master.")

    from app.models.coordinate_repair import CoordinateRepair
    from app.models.master_sisa import CleanedMasterRecord
    from app.models.upload import SourceRecord

    db.query(CoordinateRepair).filter(CoordinateRepair.batch_id == batch_id).delete(synchronize_session=False)
    db.query(CleanedMasterRecord).filter(CleanedMasterRecord.batch_id == batch_id).delete(synchronize_session=False)
    db.query(SourceRecord).filter(SourceRecord.batch_id == batch_id).delete(synchronize_session=False)
    # Delete sheet_import via bulk (not ORM instance) so FK to upload_batches is gone before batch delete.
    db.query(UploadSheetImport).filter(UploadSheetImport.id == sheet_import.id).delete(synchronize_session=False)
    db.query(UploadBatch).filter(UploadBatch.id == batch_id).delete(synchronize_session=False)
    db.commit()
    return {"message": "Sheet import berhasil dihapus"}


@router.post("/files/{file_id}/import-sheet")
@report_progress
def import_sheet(
    file_id: int,
    req: SheetRequest,
    db: DbSession,
    progress: Annotated[UploadProgress, Depends(track_upload)],
) -> dict[str, Any]:
    try:
        progress.stage("preparing")
        progress.checkpoint()
        lock_review_session(db)
        archive = (
            db.query(UploadFileArchive)
            .filter_by(id=file_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if archive is None:
            raise HTTPException(404, "Berkas dalam riwayat tidak ditemukan")
        name = selected_sheet(archive, req.sheet_name)
        existing = (
            db.query(UploadSheetImport)
            .filter_by(
                file_id=file_id,
                dataset_type=req.dataset_type.value,
                sheet_key=name or "",
                period_key=req.period or "",
            )
            .first()
        )
        if existing:
            batch = db.get(UploadBatch, existing.batch_id)
            assert batch is not None
            if batch.status == BatchStatus.PROCESSING:
                raise HTTPException(
                    409,
                    "Sheet masih diproses atau dijeda. Lanjutkan proses yang sedang berjalan.",
                )
            if batch.status != BatchStatus.FAILED:
                return {
                    "id": batch.id,
                    "status": batch.status,
                    "filename": batch.filename,
                }
        path = archive_path(archive.storage_key)
        if not path.is_file():
            raise HTTPException(
                410, "Berkas asli tidak tersedia. Unggah kembali berkas yang sama."
            )

        def attach_import(batch: UploadBatch) -> None:
            # Persist the unique sheet link together with any pause checkpoint.
            db.add(
                UploadSheetImport(
                    file_id=file_id,
                    batch_id=batch.id,
                    dataset_type=req.dataset_type.value,
                    sheet_key=name or "",
                    period_key=req.period or "",
                )
            )

        with path.open("rb") as source:
            batch = import_raw_sheet(
                db,
                source,
                archive.filename,
                req.dataset_type,
                name,
                req.period,
                progress=progress,
                on_batch=attach_import,
                existing_batch=batch if existing else None,
            )
        progress.stage("saving", batch.total_rows)
        progress.update(batch.total_rows)
        progress.checkpoint(db)
        db.commit()
        return {"id": batch.id, "status": batch.status, "filename": batch.filename}
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "sheet") from exc
    except (OSError, ValueError, ImportError, BadZipFile) as exc:
        db.rollback()
        raise HTTPException(400, f"Sheet tidak dapat disimpan: {exc!s}") from exc
    finally:
        # An interrupted transaction can be retried from its last committed chunk.
        if progress.checkpoint_committed and progress.batch_id is not None:
            db.rollback()
            interrupted = db.get(UploadBatch, progress.batch_id)
            if interrupted is not None and interrupted.status == BatchStatus.PROCESSING:
                interrupted.status = BatchStatus.FAILED
                db.commit()
