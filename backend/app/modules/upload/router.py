import csv
import os
from itertools import islice
from typing import Annotated, Any
from zipfile import BadZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models.correction import (
    CorrectionAttempt,
    CorrectionCandidateEvidence,
    CorrectionCheck,
    CorrectionTarget,
)
from ...models.correction_decision import CorrectionDecision
from ...models.master_sisa import CleanedMasterRecord, MasterSisaRecord, MasterSnapshot
from ...models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from ...models.pdpj import PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow
from ...models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from ...models.upload_file import UploadFileArchive, UploadSheetImport
from ...models.coordinate_repair import CoordinateRepair
from ...schemas.upload import BatchProcessRequest, MappingRequest, UploadBatchResponse
from ...tasks.spatial_tasks import (
    execute_batch_reconciliation_pipeline,
    mark_process_failed,
)
from ..pdpj.service import lock_review_session
from ..spatial.engine import run_spatial_matching_job
from ..spatial.master_builder import build_combined_master
from ..spatial.pipeline import execute_pipeline, pin_pipeline_sources
from ..spatial.preparation import process_master_sisa_exclusion
from .normalization import (
    extract_standard_fields,
    validate_fields,
    validate_mapping,
)
from .reader import IMPORT_CHUNK_ROWS, check_file_size, read_upload
from .storage import database_write_error
from .ingestion import import_raw_sheet
from .archive import router as archive_router, archive_path

DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.get("/batches")
async def list_batches(db: DbSession):
    batches = db.query(UploadBatch).order_by(UploadBatch.id.desc()).all()
    return [
        {
            "id": b.id,
            "filename": b.filename,
            "dataset_type": b.dataset_type,
            "status": b.status,
            "total_rows": b.total_rows,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]


@router.post("/seed-dummy")
def seed_dummy_data(db: DbSession):
    """
    Memasukkan data dummy sesuai alur riil PLN:
    1. ACMT RBM (Pascabayar multi-bulan) + LPB (Prabayar multi-bulan)
    2. Cleaning & Deduplikasi -> Master Bersih (Paska + Pra)
    3. Exclude PDPJ (yang sudah verif) -> Master Sisa
    4. Koordinat Kosong (IDPEL kosong/tidak ditemukan) dicocokkan ke Master Sisa
    """
    try:
        # Cari folder data_dummy secara robust
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        # Naiki folder sampai menemukan folder data_dummy
        dummy_dir = None
        check_dir = cur_dir
        for _ in range(6):
            candidate = os.path.join(check_dir, "data_dummy")
            if os.path.exists(candidate) and os.path.isdir(candidate):
                dummy_dir = candidate
                break
            parent = os.path.dirname(check_dir)
            if parent == check_dir:
                break
            check_dir = parent

        if not dummy_dir:
            dummy_dir = r"D:\Documents\PKL - PLN\PROJECT\sintesis\data_dummy"

        # 1. Upload & Simpan Raw ACMT RBM (Pascabayar)
        acmt_batch = UploadBatch(
            filename="acmt_pascabayar.csv",
            dataset_type=DatasetType.PASCABAYAR,
            status=BatchStatus.COMPLETED,
        )
        db.add(acmt_batch)
        db.commit()
        db.refresh(acmt_batch)

        with open(
            os.path.join(dummy_dir, "acmt_pascabayar.csv"), mode="r", encoding="utf-8"
        ) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = SourceRecord(
                    batch_id=acmt_batch.id, idpel=row.get("IDPELANGGAN"), data=dict(row)
                )
                db.add(rec)
        db.commit()

        # 2. Upload & Simpan Raw LPB (Prabayar)
        lpb_batch = UploadBatch(
            filename="lpb_prabayar.csv",
            dataset_type=DatasetType.PRABAYAR,
            status=BatchStatus.COMPLETED,
        )
        db.add(lpb_batch)
        db.commit()
        db.refresh(lpb_batch)

        with open(
            os.path.join(dummy_dir, "lpb_prabayar.csv"), mode="r", encoding="utf-8"
        ) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = SourceRecord(
                    batch_id=lpb_batch.id, idpel=row.get("IDPELANGGAN"), data=dict(row)
                )
                db.add(rec)
        db.commit()

        # 3. Bentuk Master Bersih: Cleaning data bertumpuk multi-bulan & gabung Paska + Pra
        res_master = build_combined_master(
            db=db,
            pascabayar_batch_ids=[acmt_batch.id],
            prabayar_batch_ids=[lpb_batch.id],
        )
        master_batch_id = res_master["master_batch_id"]

        # 4. Upload & Simpan PDPJ (Data yang sudah verif)
        pdpj_batch = UploadBatch(
            filename="pdpj_verif.csv",
            dataset_type=DatasetType.PDPJ,
            status=BatchStatus.COMPLETED,
        )
        db.add(pdpj_batch)
        db.commit()
        db.refresh(pdpj_batch)

        with open(
            os.path.join(dummy_dir, "pdpj_verif.csv"), mode="r", encoding="utf-8"
        ) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = SourceRecord(
                    batch_id=pdpj_batch.id, idpel=row.get("IDPELANGGAN"), data=dict(row)
                )
                db.add(rec)
        db.commit()

        # 5. Exclude yang sudah valid dari Master -> menghasilkan Master Sisa
        res_prep = process_master_sisa_exclusion(db, master_batch_id, pdpj_batch.id)

        # 6. Upload Data Koordinat Kosong (Target lapangan IDPEL kosong/tidak ditemukan)
        target_batch = UploadBatch(
            filename="koordinat_kosong.csv",
            dataset_type=DatasetType.KOORDINAT_KOSONG,
            status=BatchStatus.COMPLETED,
        )
        db.add(target_batch)
        db.commit()
        db.refresh(target_batch)

        with open(
            os.path.join(dummy_dir, "koordinat_kosong.csv"), mode="r", encoding="utf-8"
        ) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = SourceRecord(batch_id=target_batch.id, data=dict(row))
                db.add(rec)
        db.commit()

        # 7. Cocokkan data IDPEL Kosong sama Master yang sudah di-exclude valid
        res_matching = run_spatial_matching_job(
            db=db,
            process_name="Pencocokan Koordinat Kosong vs Master Sisa",
            target_batch_id=target_batch.id,
            radius_meters=150.0,
            max_candidates_per_target=5,
            master_snapshot_id=res_prep["master_snapshot_id"],
        )

        return {
            "message": "Alur PLN Berhasil Dieksekusi: Master dibentuk, PDPJ diexclude, & Koordinat Kosong dicocokkan!",
            "pascabayar_batch_id": acmt_batch.id,
            "prabayar_batch_id": lpb_batch.id,
            "master_batch_id": master_batch_id,
            "pdpj_batch_id": pdpj_batch.id,
            "koordinat_kosong_batch_id": target_batch.id,
            "process_id": res_matching.get("process_id"),
            "master_cleaning_summary": res_master,
            "exclusion_summary": res_prep,
            "matching_summary": res_matching,
        }
    except (OSError, ValueError, SQLAlchemyError) as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal memuat data dummy: {e!s}")


@router.post("/batch-process")
async def batch_process_endpoint(req: BatchProcessRequest, db: DbSession) -> dict:
    """Pin source datasets before dispatching the shared reconciliation pipeline."""
    try:
        sources = pin_pipeline_sources(
            db,
            req.pascabayar_batch_id,
            req.prabayar_batch_id,
            req.pdpj_batch_id,
            req.target_batch_id,
            req.dil_batch_id,
            req.pdpj_review_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    process = ReconciliationProcess(
        process_name="Proses Rekonsiliasi Staged (Multi-Dataset)",
        radius_meters=req.radius_meters,
        source_batches=sources,
        matching_status=ProcessStatus.QUEUED,
        review_status=ReviewStatus.NOT_STARTED,
    )
    db.add(process)
    db.commit()
    try:
        execute_batch_reconciliation_pipeline.delay(process_id=process.id)
        return {
            "status": "queued",
            "process_id": process.id,
            "execution_mode": "async_celery",
            "matching_summary": {"process_id": process.id, "status": "queued"},
        }
    except Exception as exc:
        if not settings.ALLOW_SYNC_FALLBACK:
            mark_process_failed(db, process.id)
            raise HTTPException(
                status_code=503, detail="Worker tidak tersedia"
            ) from exc
    try:
        result = execute_pipeline(db, process.id)
        return {
            "status": result["status"],
            "process_id": process.id,
            "execution_mode": "sync_fallback",
            "matching_summary": result,
        }
    except Exception as exc:
        mark_process_failed(db, process.id)
        raise HTTPException(status_code=500, detail="Gagal memproses batch") from exc


@router.post("/auto-pipeline")
async def auto_pipeline_endpoint(batch_id: int, db: DbSession) -> dict:
    """Create a separate process and snapshot; existing processes stay unchanged."""
    batch = db.get(UploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")
    if batch.status != BatchStatus.COMPLETED:
        raise HTTPException(
            status_code=422, detail="Konfirmasi mapping batch terlebih dahulu"
        )
    try:
        sources = pin_pipeline_sources(
            db,
            batch.id if batch.dataset_type == DatasetType.PASCABAYAR else None,
            batch.id if batch.dataset_type == DatasetType.PRABAYAR else None,
            batch.id if batch.dataset_type == DatasetType.PDPJ else None,
            batch.id
            if batch.dataset_type in {DatasetType.TARGET, DatasetType.KOORDINAT_KOSONG}
            else None,
            dil_batch_id=batch.id if batch.dataset_type == DatasetType.DIL else None,
        )
        process = ReconciliationProcess(
            process_name=f"Pencocokan Otomatis #{batch.id}",
            source_batches=sources,
            radius_meters=150,
            matching_status=ProcessStatus.QUEUED,
        )
        db.add(process)
        db.commit()
        result = execute_pipeline(db, process.id)
        return {
            **result,
            "action": "matched" if sources["target"] else "master_updated",
            "message": "Pemrosesan dataset selesai",
            "total_candidates": result.get("total_candidates_found", 0),
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/reset")
async def reset_database(db: DbSession):
    """Menghapus semua data upload, kandidat, dan riwayat untuk pengujian ulang."""
    try:
        archive_keys = [key for (key,) in db.query(UploadFileArchive.storage_key).all()]
        db.query(CoordinateRepair).delete()
        db.query(UploadSheetImport).delete()
        db.query(CorrectionDecision).delete()
        db.query(CorrectionCandidateEvidence).delete()
        db.query(CorrectionTarget).delete()
        db.query(CorrectionAttempt).delete()
        db.query(CorrectionCheck).delete()
        db.query(PdpjChange).delete()
        db.query(PdpjRecommendation).delete()
        db.query(PdpjRow).delete()
        db.query(PdpjReview).delete()
        db.query(MatchCandidate).delete()
        db.query(MatchingRun).delete()
        db.query(ReconciliationProcess).delete()
        db.query(MasterSisaRecord).delete()
        db.query(MasterSnapshot).delete()
        db.query(CleanedMasterRecord).delete()
        db.query(SourceRecord).delete()
        db.query(UploadBatch).delete()
        db.query(UploadFileArchive).delete()
        db.commit()
        for key in archive_keys:
            try:
                archive_path(key).unlink(missing_ok=True)
            except OSError:
                pass  # Reference rows are already removed; do not undo a successful reset.
        return {"message": "Semua data berhasil direset. Database kembali bersih."}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal reset database: {e!s}")


@router.post("/preview")
def preview_file(
    file: Annotated[UploadFile, File()],
    sheet_name: Annotated[str | None, Form(max_length=128)] = None,
) -> dict[str, Any]:
    """Read a bounded preview using the importer, without creating a batch."""
    try:
        check_file_size(file.file)
        with read_upload(file.file, file.filename or "", sheet_name) as (
            selected_sheet,
            rows,
        ):
            preview = list(islice(rows, 5))
            if not preview:
                raise ValueError(
                    f"Sheet '{selected_sheet}' tidak memiliki baris data setelah nama kolom"
                )
            return {
                "headers": list(preview[0][1]),
                "rows": [row for _, row in preview],
                "headerRow": preview[0][0] - 1,
                "source_sheet": selected_sheet,
            }
    except (OSError, ValueError, ImportError, BadZipFile) as exc:
        raise HTTPException(
            status_code=400, detail=f"Gagal membaca pratinjau: {exc!s}"
        ) from exc
    finally:
        file.file.close()


@router.post("/", response_model=UploadBatchResponse)
def upload_file(
    dataset_type: Annotated[DatasetType, Form()],
    file: Annotated[UploadFile, File()],
    db: DbSession,
    period: Annotated[str | None, Form(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
    sheet_name: Annotated[str | None, Form(max_length=128)] = None,
):
    try:
        check_file_size(file.file)
        batch = import_raw_sheet(
            db, file.file, file.filename or "", dataset_type, sheet_name, period,
            chunk_rows=IMPORT_CHUNK_ROWS,
        )
        # A late parser/insert failure must leave no partial batch behind.
        db.commit()
        db.refresh(batch)
        return batch
    except (OSError, ValueError, ImportError, BadZipFile) as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Gagal membaca file: {exc!s}"
        ) from exc
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "unggahan") from exc
    finally:
        file.file.close()


@router.post("/confirm-mapping")
def confirm_mapping(req: MappingRequest, db: DbSession) -> dict:
    """Validate mapping and rows, preserving the original cells for traceability."""
    try:
        return apply_mapping(req, db)
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "konfirmasi mapping") from exc


def apply_mapping(req: MappingRequest, db: Session) -> dict:
    """Keep derived fields and batch completion in the same transaction."""
    lock_review_session(db)
    batch = (
        db.query(UploadBatch)
        .filter(UploadBatch.id == req.batch_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")
    in_use = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.target_batch_id == batch.id)
        .first()
        or db.query(MasterSnapshot)
        .filter(
            (MasterSnapshot.master_batch_id == batch.id)
            | (MasterSnapshot.pdpj_batch_id == batch.id)
        )
        .first()
    )
    queued_sources = (
        db.query(ReconciliationProcess.source_batches)
        .filter(ReconciliationProcess.source_batches.isnot(None))
        .all()
    )
    pinned = any(
        batch.id
        in (
            sources.get("pascabayar", [])
            + sources.get("prabayar", [])
            + sources.get("dil", [])
        )
        or batch.id in (sources.get("pdpj"), sources.get("target"))
        for (sources,) in queued_sources
    )
    review_pinned = any(
        review.batch_id == batch.id or batch.id in review.master_batch_ids
        for review in db.query(PdpjReview).all()
    )
    if (in_use or pinned or review_pinned) and (
        batch.column_mapping or {}
    ) != req.column_mapping:
        raise HTTPException(
            status_code=409,
            detail="Dataset sudah digunakan proses; unggah batch baru untuk mengubah mapping",
        )
    if (
        batch.status == BatchStatus.COMPLETED
        and db.query(UploadSheetImport).filter_by(batch_id=batch.id).first()
        and (batch.column_mapping or {}) != req.column_mapping
    ):
        raise HTTPException(
            409, "Sheet sudah disimpan dan divalidasi; pilih sheet lain atau unggah berkas yang diperbaiki"
        )
    headers: set[str] = set()
    for (data,) in (
        db.query(SourceRecord.data)
        .filter(SourceRecord.batch_id == batch.id)
        .yield_per(IMPORT_CHUNK_ROWS)
    ):
        headers.update(data or {})
    try:
        validate_mapping(req.column_mapping, headers, batch.dataset_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    valid_rows = 0
    errors: list[dict[str, Any]] = []
    last_id = 0
    total_rows = 0
    while True:
        records = (
            db.query(SourceRecord)
            .filter(SourceRecord.batch_id == batch.id, SourceRecord.id > last_id)
            .order_by(SourceRecord.id)
            .limit(IMPORT_CHUNK_ROWS)
            .all()
        )
        if not records:
            break
        for record in records:
            total_rows += 1
            row_number = record.row_number or total_rows + 1
            fields = extract_standard_fields(record.data or {}, req.column_mapping)
            fields["tglbaca"] = fields["tglbaca"] or batch.period
            record.normalized_data = {
                key: value
                for key, value in fields.items()
                if key != "validation_errors"
            }
            record.row_number = row_number
            record.idpel = fields["idpel"]
            record.validation_errors = validate_fields(fields, batch.dataset_type)
            record.is_valid = not record.validation_errors
            valid_rows += int(record.is_valid)
            if record.validation_errors and len(errors) < 100:
                errors.append(
                    {
                        "record_id": record.id,
                        "row": row_number,
                        "errors": record.validation_errors,
                    }
                )
        last_id = records[-1].id
        db.flush()
        # Release each chunk from the identity map before loading the next one.
        for record in records:
            db.expunge(record)
    batch.column_mapping = req.column_mapping
    batch.status = BatchStatus.COMPLETED
    batch.total_rows = total_rows
    batch.valid_rows = valid_rows
    batch.error_rows = total_rows - valid_rows
    db.commit()
    return {
        "message": "Mapping diterapkan dan validasi selesai",
        "batch_id": batch.id,
        "rows": batch.total_rows,
        "valid_rows": batch.valid_rows,
        "error_rows": batch.error_rows,
        "errors": errors,
    }


router.include_router(archive_router)
