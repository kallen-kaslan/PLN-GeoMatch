from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from app.models.correction import CorrectionCheck


def reject_correction_legacy_write(db: Session, process_id: int) -> None:
    """Correction choices must pass scoped revision and audit checks."""
    if db.get(CorrectionCheck, process_id) is not None:
        raise HTTPException(409, "Gunakan alur Peta Koreksi untuk pemeriksaan kategori baru")


def apply_candidate_filters(
    query,
    validity_filters: str | None,
    layanan_filters: str | None,
    idpel_filters: str | None,
):
    """Apply OR within each filter group and AND between groups."""
    validity_values = {
        value.strip().lower()
        for value in (validity_filters or "").split(",")
        if value.strip()
    }
    if validity_values:
        validity_clauses: list[ColumnElement[bool]] = []
        status_values = {
            "valid": "VALID",
            "no-idpel": "PERLU_KONFIRMASI_IDPEL",
            "luar-jangkauan": "DILUAR_RADIUS",
            "idpel-kosong": "IDPEL_KOSONG",
        }
        selected_statuses = [
            status_values[value] for value in validity_values if value in status_values
        ]
        if selected_statuses:
            validity_clauses.append(
                MatchCandidate.validity_status.in_(selected_statuses)
            )
        if "kurang-5m" in validity_values:
            validity_clauses.append(MatchCandidate.is_under_5m == 1)
        if validity_clauses:
            query = query.filter(or_(*validity_clauses))

    layanan_values = {
        value.strip().upper()
        for value in (layanan_filters or "").split(",")
        if value.strip()
    }
    if layanan_values:
        query = query.filter(MatchCandidate.jenis_layanan.in_(layanan_values))

    idpel_values = {
        value.strip().lower()
        for value in (idpel_filters or "").split(",")
        if value.strip()
    }
    if idpel_values:
        idpel_clauses: list[ColumnElement[bool]] = []
        if "ada" in idpel_values:
            idpel_clauses.append(
                (MatchCandidate.candidate_idpel != "")
                & ~MatchCandidate.candidate_idpel.like("UNASSIGNED-%")
                & ~MatchCandidate.candidate_idpel.like("DILUAR_RADIUS%")
                & (MatchCandidate.candidate_idpel != "TIDAK_DITEMUKAN")
                & (MatchCandidate.candidate_idpel != "IDPEL_KOSONG")
            )
        if "kosong" in idpel_values:
            idpel_clauses.append(
                (MatchCandidate.candidate_idpel == "")
                | (MatchCandidate.candidate_idpel == "IDPEL_KOSONG")
            )
        if "tidak-ditemukan" in idpel_values:
            idpel_clauses.append(MatchCandidate.candidate_idpel == "TIDAK_DITEMUKAN")
        if "unassigned" in idpel_values:
            idpel_clauses.append(MatchCandidate.candidate_idpel.like("UNASSIGNED-%"))
        if idpel_clauses:
            query = query.filter(or_(*idpel_clauses))

    return query


from app.config import settings
from app.database import get_db
from app.models.master_sisa import MasterSnapshot
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from app.modules.spatial.engine import (
    create_matching_run,
    lock_matching_session,
    run_spatial_matching_job,
    validate_target_batch,
)
from app.modules.spatial.master_builder import build_combined_master
from app.modules.pdpj.service import completed_review
from app.modules.spatial.preparation import (
    process_master_sisa_exclusion,
    resolve_master_snapshot,
)
from app.tasks.spatial_tasks import execute_matching_task, mark_process_failed

DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/process", tags=["Process & Matching"])


class BuildMasterRequest(BaseModel):
    pascabayar_batch_ids: list[int]  # ACMT / RBM
    prabayar_batch_ids: list[int]  # LPB
    dil_batch_ids: list[int] = Field(default_factory=list)


class PrepareMasterSisaRequest(BaseModel):
    master_batch_id: int
    pdpj_batch_id: int | None = None
    pdpj_review_id: int | None = Field(None, gt=0)


class RunMatchingRequest(BaseModel):
    process_name: str
    target_batch_id: int  # Batch Koordinat Kosong
    master_snapshot_id: int | None = Field(None, gt=0)
    radius_meters: float = Field(100.0, gt=0, allow_inf_nan=False)
    max_candidates: int = Field(5, ge=1, le=1000)


class DecisionRequest(BaseModel):
    is_accepted: int


class BulkDecisionRequest(BaseModel):
    candidate_ids: list[int]
    is_accepted: int


@router.post("/build-master")
async def build_master_endpoint(req: BuildMasterRequest, db: DbSession):
    """
    Step 1: Membersihkan data bertumpuk multi-bulan dari ACMT (pascabayar) & LPB (prabayar),
    lalu menggabungkannya menjadi Master Terpadu.
    """
    try:
        return build_combined_master(
            db=db,
            pascabayar_batch_ids=req.pascabayar_batch_ids,
            prabayar_batch_ids=req.prabayar_batch_ids,
            dil_batch_ids=req.dil_batch_ids,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/prepare-master-sisa")
async def prepare_master_sisa(req: PrepareMasterSisaRequest, db: DbSession):
    """
    Step 2: Mengecualikan data yang sudah valid/verif dari Master menggunakan data PDPJ.
    Hasilnya adalah Master Sisa.
    """
    try:
        review = completed_review(db, req.pdpj_batch_id, req.pdpj_review_id) if req.pdpj_batch_id is not None else None
        if req.pdpj_review_id is not None and review is None:
            raise ValueError("Pilih berkas PDPJ yang sesuai pemeriksaan")
        return process_master_sisa_exclusion(
            db=db, master_batch_id=req.master_batch_id, pdpj_batch_id=req.pdpj_batch_id,
            pdpj_review_id=review.id if review else None,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e


def dispatch_matching(
    db: Session, process: ReconciliationProcess, run: MatchingRun
) -> dict:
    """Dispatch the reserved run; synchronous fallback uses the same run ID."""
    process_id, run_id = process.id, run.id
    if process.target_batch_id is None:
        raise HTTPException(
            status_code=409, detail="Proses belum memiliki batch target"
        )
    db.commit()
    try:
        execute_matching_task.delay(
            process_id=process_id,
            process_name=process.process_name,
            target_batch_id=process.target_batch_id,
            radius_meters=run.radius_meters,
            max_candidates_per_target=run.max_candidates,
            run_id=run_id,
        )
        return {
            "process_id": process_id,
            "process_name": process.process_name,
            "run_id": run_id,
            "generation": run.generation,
            "master_snapshot_id": process.master_snapshot_id,
            "status": "queued",
            "execution_mode": "async_celery",
        }
    except Exception as exc:
        if not settings.ALLOW_SYNC_FALLBACK:
            mark_process_failed(db, process_id, run_id)
            raise HTTPException(
                status_code=503, detail="Worker tidak tersedia"
            ) from exc
    try:
        result = run_spatial_matching_job(
            db,
            process.process_name,
            process.target_batch_id,
            process_id=process_id,
            run_id=run_id,
        )
        return {**result, "execution_mode": "sync_fallback"}
    except Exception as exc:
        mark_process_failed(db, process_id, run_id)
        raise HTTPException(status_code=500, detail="Pencocokan gagal") from exc


@router.get("/master-snapshots")
async def list_master_snapshots(db: DbSession) -> list[dict]:
    """Expose immutable source IDs for explicit matching requests."""
    return [
        {
            "id": snapshot.id,
            "master_batch_id": snapshot.master_batch_id,
            "pdpj_batch_id": snapshot.pdpj_batch_id,
            "created_at": snapshot.created_at,
        }
        for snapshot in db.query(MasterSnapshot)
        .order_by(MasterSnapshot.id.desc())
        .all()
    ]


@router.post("/run-matching")
async def run_matching(req: RunMatchingRequest, db: DbSession) -> dict:
    """Bind both sources before enqueueing so later uploads cannot change a job."""
    try:
        validate_target_batch(db, req.target_batch_id)
        snapshot = resolve_master_snapshot(db, req.master_snapshot_id)
        process = ReconciliationProcess(
            process_name=req.process_name,
            radius_meters=req.radius_meters,
            master_snapshot_id=snapshot.id,
            target_batch_id=req.target_batch_id,
            matching_status=ProcessStatus.QUEUED,
            review_status=ReviewStatus.NOT_STARTED,
        )
        db.add(process)
        db.flush()
        run = create_matching_run(db, process, req.radius_meters, req.max_candidates)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return dispatch_matching(db, process, run)


class RerunRequest(BaseModel):
    radius_meters: float = Field(100.0, gt=0, allow_inf_nan=False)
    max_candidates: int = Field(5, ge=1, le=1000)


@router.post("/{process_id}/rerun")
async def rerun_matching(process_id: int, req: RerunRequest, db: DbSession) -> dict:
    """Create a new search generation; keep all prior candidates and decisions."""
    reject_correction_legacy_write(db, process_id)
    process = db.get(ReconciliationProcess, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Proses tidak ditemukan")
    try:
        run = create_matching_run(db, process, req.radius_meters, req.max_candidates)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return dispatch_matching(db, process, run)


@router.get("/{process_id}/runs")
async def list_matching_runs(process_id: int, db: DbSession) -> list[dict]:
    """Inspect every search attempt including historical radius and completion."""
    process = db.get(ReconciliationProcess, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Proses tidak ditemukan")
    return [
        {
            "id": run.id,
            "generation": run.generation,
            "status": run.status,
            "radius_meters": run.radius_meters,
            "max_candidates": run.max_candidates,
            "total_targets": run.total_targets,
            "matched_targets": run.matched_targets,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
            "is_current": run.generation == process.current_generation,
        }
        for run in db.query(MatchingRun)
        .filter(MatchingRun.process_id == process_id)
        .order_by(MatchingRun.generation.desc())
        .all()
    ]


@router.get("/{process_id}/candidates")
async def get_candidates(
    process_id: int,
    db: DbSession,
    status_filter: int | None = Query(None),
    generation: int | None = Query(None, ge=1),
    validity_filters: str | None = Query(None),
    layanan_filters: str | None = Query(None),
    idpel_filters: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    process = db.get(ReconciliationProcess, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Proses tidak ditemukan")
    selected_generation = (
        process.current_generation if generation is None else generation
    )
    if (
        generation is not None
        and not db.query(MatchingRun)
        .filter(
            MatchingRun.process_id == process_id, MatchingRun.generation == generation
        )
        .first()
    ):
        raise HTTPException(status_code=404, detail="Versi pencarian tidak ditemukan")
    query = db.query(MatchCandidate).filter(
        MatchCandidate.process_id == process_id,
        MatchCandidate.generation == selected_generation,
    )

    # Multi-select data-eligibility filters
    query = apply_candidate_filters(
        query, validity_filters, layanan_filters, idpel_filters
    )

    # Existing single-select review status filter
    if status_filter is not None:
        query = query.filter(MatchCandidate.is_accepted == status_filter)

    total_count = query.count()
    candidates = (
        query.order_by(MatchCandidate.target_ref, MatchCandidate.rank)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "process_id": process_id,
        "generation": selected_generation,
        "total": total_count,
        "items": candidates,
        "skip": skip,
        "limit": limit,
    }


def ensure_current_candidate(db: Session, candidate: MatchCandidate) -> None:
    """Historical decisions remain read-only after publishing a newer attempt."""
    lock_matching_session(db)
    reject_correction_legacy_write(db, candidate.process_id)
    process = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.id == candidate.process_id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if process is None or candidate.generation != process.current_generation:
        raise HTTPException(
            status_code=409, detail="Kandidat berasal dari versi pencarian historis"
        )


@router.post("/candidates/bulk-decision")
async def submit_bulk_candidate_decision(req: BulkDecisionRequest, db: DbSession):
    if not req.candidate_ids:
        raise HTTPException(status_code=400, detail="candidate_ids tidak boleh kosong")
    if req.is_accepted not in (0, 1):
        raise HTTPException(status_code=422, detail="is_accepted hanya boleh 0 atau 1")

    candidates = (
        db.query(MatchCandidate).filter(MatchCandidate.id.in_(req.candidate_ids)).all()
    )
    if len(candidates) != len(set(req.candidate_ids)):
        raise HTTPException(status_code=404, detail="Kandidat tidak ditemukan")
    for candidate in candidates:
        ensure_current_candidate(db, candidate)

    updated_count = (
        db.query(MatchCandidate)
        .filter(MatchCandidate.id.in_(req.candidate_ids))
        .update({"is_accepted": req.is_accepted})
    )

    db.commit()
    return {
        "message": "Keputusan massal berhasil disimpan",
        "updated_count": updated_count,
        "is_accepted": req.is_accepted,
    }


@router.post("/candidates/{candidate_id}/decision")
async def submit_candidate_decision(
    candidate_id: int, req: DecisionRequest, db: DbSession
):
    cand = db.query(MatchCandidate).filter(MatchCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Kandidat tidak ditemukan")

    ensure_current_candidate(db, cand)
    if req.is_accepted not in (-1, 0, 1):
        raise HTTPException(status_code=422, detail="Keputusan kandidat tidak valid")
    cand.is_accepted = req.is_accepted
    db.commit()
    return {
        "message": "Keputusan berhasil disimpan",
        "candidate_id": candidate_id,
        "is_accepted": cand.is_accepted,
    }


@router.post("/{process_id}/finalize-review")
async def finalize_review(process_id: int, db: DbSession):
    reject_correction_legacy_write(db, process_id)
    process = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.id == process_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=404, detail="Proses tidak ditemukan")
    if process.review_status == ReviewStatus.FINALIZED:
        return {
            "message": "Review sudah final",
            "review_status": process.review_status,
            "already_finalized": True,
        }
    process.review_status = ReviewStatus.FINALIZED
    db.commit()
    return {
        "message": "Review finalisasi berhasil",
        "review_status": process.review_status,
        "already_finalized": False,
    }
