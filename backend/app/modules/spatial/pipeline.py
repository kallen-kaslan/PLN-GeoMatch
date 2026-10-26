"""One pipeline shared by HTTP fallback and Celery, with sources pinned at submission."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.matching import MatchingRun, ProcessStatus, ReconciliationProcess
from app.models.upload import BatchStatus, DatasetType, UploadBatch
from app.modules.pdpj.service import completed_review
from app.modules.spatial.engine import lock_matching_session, run_spatial_matching_job
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.preparation import process_master_sisa_exclusion


def pin_pipeline_sources(
    db: Session,
    pascabayar_batch_id: int | None,
    prabayar_batch_id: int | None,
    pdpj_batch_id: int | None,
    target_batch_id: int | None,
    dil_batch_id: int | None = None,
    pdpj_review_id: int | None = None,
    correction_category: str | None = None,
) -> dict[str, Any]:
    """Resolve optional defaults now; workers must never select new uploads later."""

    def selected(batch_id: int | None, types: list[DatasetType]) -> int | None:
        if batch_id is not None:
            batch = db.get(UploadBatch, batch_id)
            if (
                batch is None
                or batch.dataset_type not in types
                or batch.status != BatchStatus.COMPLETED
            ):
                raise ValueError(
                    "Batch sumber tidak ditemukan, belum selesai, atau jenisnya tidak sesuai"
                )
        else:
            batch = (
                db.query(UploadBatch)
                .filter(
                    UploadBatch.dataset_type.in_(types),
                    UploadBatch.status == BatchStatus.COMPLETED,
                )
                .order_by(UploadBatch.id.desc())
                .first()
            )
        return batch.id if batch else None

    pasca = [pascabayar_batch_id] if pascabayar_batch_id is not None else []
    pra = [prabayar_batch_id] if prabayar_batch_id is not None else []
    dil = [dil_batch_id] if dil_batch_id is not None else []
    if not pasca and not pra and not dil:
        for types, ids in (
            ([DatasetType.PASCABAYAR], pasca),
            ([DatasetType.PRABAYAR], pra),
            ([DatasetType.DIL], dil),
        ):
            ids.extend(
                batch.id
                for batch in db.query(UploadBatch)
                .filter(
                    UploadBatch.dataset_type.in_(types),
                    UploadBatch.status == BatchStatus.COMPLETED,
                )
                .order_by(UploadBatch.id)
                .all()
            )
    for batch_id in pasca:
        selected(batch_id, [DatasetType.PASCABAYAR])
    for batch_id in pra:
        selected(batch_id, [DatasetType.PRABAYAR])
    for batch_id in dil:
        selected(batch_id, [DatasetType.DIL])
    if not pasca and not pra and not dil:
        raise ValueError(
            "Unggah dan konfirmasi minimal satu batch master terlebih dahulu"
        )
    pdpj_id = selected(pdpj_batch_id, [DatasetType.PDPJ])
    review = (
        completed_review(db, pdpj_id, pdpj_review_id) if pdpj_id is not None else None
    )
    if pdpj_review_id is not None and review is None:
        raise ValueError("Pilih berkas PDPJ yang sesuai pemeriksaan")
    if review is not None:
        if any(
            value is not None
            for value in (pascabayar_batch_id, prabayar_batch_id, dil_batch_id)
        ) and set(pasca + pra + dil) != set(review.master_batch_ids):
            raise ValueError(
                "Sumber master berbeda dari pemeriksaan PDPJ; jalankan validasi ulang dengan sumber tersebut"
            )
        else:
            pasca, pra, dil = [], [], []
            for batch_id in review.master_batch_ids:
                batch = db.get(UploadBatch, batch_id)
                assert batch is not None
                {
                    DatasetType.PASCABAYAR: pasca,
                    DatasetType.PRABAYAR: pra,
                    DatasetType.DIL: dil,
                }[batch.dataset_type].append(batch_id)
    target_id = selected(
        target_batch_id,
        [
            DatasetType.KOORDINAT_KOSONG,
            DatasetType.TARGET,
            DatasetType.IDPEL_TIDAK_KETEMU,
            DatasetType.IDPEL_KOSONG,
        ],
    )
    target = db.get(UploadBatch, target_id) if target_id is not None else None
    if (
        target
        and target.dataset_type
        in {
            DatasetType.IDPEL_TIDAK_KETEMU,
            DatasetType.IDPEL_KOSONG,
        }
        and (correction_category != target.dataset_type.value or review is None)
    ):
        raise ValueError(
            "Gunakan menu Data Koreksi dan pilih PDPJ yang sudah selesai divalidasi"
        )
    return {
        "pascabayar": pasca,
        "prabayar": pra,
        "dil": dil,
        "pdpj": pdpj_id,
        "pdpj_review_id": review.id if review else None,
        "target": target_id,
    }


def execute_pipeline(
    db: Session, process_id: int, run_id: int | None = None
) -> dict[str, Any]:
    """Prepare only this process's snapshot and preserve completed search attempts."""
    lock_matching_session(db)
    process = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.id == process_id)
        .with_for_update()
        .first()
    )
    if process is None or not process.source_batches:
        raise ValueError("Proses atau sumber dataset tidak ditemukan")
    sources = process.source_batches
    if process.master_snapshot_id is None:
        master = build_combined_master(
            db,
            sources["pascabayar"],
            sources["prabayar"],
            sources.get("dil", []),
            commit=False,
        )
        prepared = process_master_sisa_exclusion(
            db,
            master["master_batch_id"],
            sources["pdpj"],
            commit=False,
            pdpj_review_id=sources.get("pdpj_review_id"),
        )
        process.master_snapshot_id = prepared["master_snapshot_id"]
        process.target_batch_id = sources["target"]
        db.flush()
    if process.target_batch_id is None:
        process.matching_status = ProcessStatus.COMPLETED
        process.completed_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        return {
            "process_id": process.id,
            "status": "completed",
            "total_targets": 0,
            "master_snapshot_id": process.master_snapshot_id,
        }
    latest_run = (
        db.query(MatchingRun)
        .filter(MatchingRun.process_id == process.id)
        .order_by(MatchingRun.generation.desc())
        .first()
    )
    return run_spatial_matching_job(
        db,
        process.process_name,
        process.target_batch_id,
        radius_meters=process.radius_meters,
        process_id=process.id,
        run_id=run_id if run_id is not None else latest_run.id if latest_run else None,
    )
