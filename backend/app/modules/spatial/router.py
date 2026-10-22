from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import List, Optional


def apply_candidate_filters(query, validity_filters: Optional[str], layanan_filters: Optional[str], idpel_filters: Optional[str]):
    """Apply OR within each filter group and AND between groups."""
    validity_values = {value.strip().lower() for value in (validity_filters or "").split(",") if value.strip()}
    if validity_values:
        validity_clauses = []
        status_values = {
            "valid": "VALID",
            "no-idpel": "PERLU_KONFIRMASI_IDPEL",
            "luar-jangkauan": "DILUAR_RADIUS",
            "idpel-kosong": "IDPEL_KOSONG",
        }
        selected_statuses = [status_values[value] for value in validity_values if value in status_values]
        if selected_statuses:
            validity_clauses.append(MatchCandidate.validity_status.in_(selected_statuses))
        if "kurang-5m" in validity_values:
            validity_clauses.append(MatchCandidate.is_under_5m == 1)
        if validity_clauses:
            query = query.filter(or_(*validity_clauses))

    layanan_values = {value.strip().upper() for value in (layanan_filters or "").split(",") if value.strip()}
    if layanan_values:
        query = query.filter(MatchCandidate.jenis_layanan.in_(layanan_values))

    idpel_values = {value.strip().lower() for value in (idpel_filters or "").split(",") if value.strip()}
    if idpel_values:
        idpel_clauses = []
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
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.preparation import process_master_sisa_exclusion
from app.modules.spatial.engine import run_spatial_matching_job
from app.models.matching import MatchCandidate, ReconciliationProcess, ProcessStatus, ReviewStatus
from app.tasks.spatial_tasks import execute_matching_task

router = APIRouter(prefix="/process", tags=["Process & Matching"])

class BuildMasterRequest(BaseModel):
    pascabayar_batch_ids: List[int] # ACMT / RBM
    prabayar_batch_ids: List[int]   # LPB

class PrepareMasterSisaRequest(BaseModel):
    master_batch_id: int
    pdpj_batch_id: int

class RunMatchingRequest(BaseModel):
    process_name: str
    target_batch_id: int # Batch Koordinat Kosong
    radius_meters: float = 100.0
    max_candidates: int = 5

class DecisionRequest(BaseModel):
    is_accepted: int

class BulkDecisionRequest(BaseModel):
    candidate_ids: List[int]
    is_accepted: int

@router.post("/build-master")
async def build_master_endpoint(req: BuildMasterRequest, db: Session = Depends(get_db)):
    """
    Step 1: Membersihkan data bertumpuk multi-bulan dari ACMT (pascabayar) & LPB (prabayar),
    lalu menggabungkannya menjadi Master Terpadu.
    """
    try:
        return build_combined_master(
            db=db,
            pascabayar_batch_ids=req.pascabayar_batch_ids,
            prabayar_batch_ids=req.prabayar_batch_ids
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/prepare-master-sisa")
async def prepare_master_sisa(req: PrepareMasterSisaRequest, db: Session = Depends(get_db)):
    """
    Step 2: Mengecualikan data yang sudah valid/verif dari Master menggunakan data PDPJ.
    Hasilnya adalah Master Sisa.
    """
    try:
        return process_master_sisa_exclusion(
            db=db,
            master_batch_id=req.master_batch_id,
            pdpj_batch_id=req.pdpj_batch_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run-matching")
async def run_matching(req: RunMatchingRequest, db: Session = Depends(get_db)):
    """
    Step 3: Mencocokkan data Koordinat Kosong (IDPEL kosong/tidak ditemukan)
    dengan Master Sisa berdasarkan radius geografis.
    Membuat record dengan status QUEUED, lalu mendispatch ke Celery background worker.
    Jika broker tidak tersedia, fallback transparan ke eksekusi sinkron langsung.
    """
    process = ReconciliationProcess(
        process_name=req.process_name,
        radius_meters=req.radius_meters,
        matching_status=ProcessStatus.QUEUED,
        review_status=ReviewStatus.NOT_STARTED,
    )
    db.add(process)
    db.commit()
    db.refresh(process)

    # Coba dispatch ke Celery worker
    try:
        execute_matching_task.delay(
            process_id=process.id,
            process_name=req.process_name,
            target_batch_id=req.target_batch_id,
            radius_meters=req.radius_meters,
            max_candidates_per_target=req.max_candidates
        )
        return {
            "process_id": process.id,
            "process_name": process.process_name,
            "status": "queued",
            "execution_mode": "async_celery",
            "message": "Pencocokan spasial berhasil diantrekan ke Celery background worker."
        }
    except Exception as exc:
        # Jika dispatch gagal:
        if not settings.ALLOW_SYNC_FALLBACK:
            process.matching_status = ProcessStatus.FAILED
            db.commit()
            raise HTTPException(
                status_code=503,
                detail=f"Celery worker/Redis broker tidak tersedia ({str(exc)}). "
                       f"Nyalakan Redis atau set ALLOW_SYNC_FALLBACK=True untuk mode development."
            )

        # Fallback sync eksplisit terproteksi ALLOW_SYNC_FALLBACK
        try:
            process.matching_status = ProcessStatus.RUNNING
            db.commit()
            res = run_spatial_matching_job(
                db=db,
                process_name=req.process_name,
                target_batch_id=req.target_batch_id,
                radius_meters=req.radius_meters,
                max_candidates_per_target=req.max_candidates,
                process_id=process.id
            )
            res["execution_mode"] = "sync_fallback"
            return res
        except Exception as e:
            process.matching_status = ProcessStatus.FAILED
            db.commit()
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/{process_id}/candidates")
async def get_candidates(
    process_id: int,
    db: Session = Depends(get_db),
    status_filter: Optional[int] = Query(None),
    validity_filters: Optional[str] = Query(None),
    layanan_filters: Optional[str] = Query(None),
    idpel_filters: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000)
):
    query = db.query(MatchCandidate).filter(MatchCandidate.process_id == process_id)

    # Multi-select data-eligibility filters
    query = apply_candidate_filters(query, validity_filters, layanan_filters, idpel_filters)

    # Existing single-select review status filter
    if status_filter is not None:
        query = query.filter(MatchCandidate.is_accepted == status_filter)

    total_count = query.count()
    candidates = query.order_by(MatchCandidate.target_ref, MatchCandidate.rank).offset(skip).limit(limit).all()

    # Fallback: jika process_id spesifik tidak ada kandidat, cari proses yang ada datanya
    if not candidates and skip == 0:
        latest_with_data = (
            db.query(ReconciliationProcess)
            .join(MatchCandidate, MatchCandidate.process_id == ReconciliationProcess.id)
            .order_by(ReconciliationProcess.id.desc())
            .first()
        )
        if latest_with_data and latest_with_data.id != process_id:
            query = db.query(MatchCandidate).filter(MatchCandidate.process_id == latest_with_data.id)
            query = apply_candidate_filters(query, validity_filters, layanan_filters, idpel_filters)
            if status_filter is not None:
                query = query.filter(MatchCandidate.is_accepted == status_filter)

            total_count = query.count()
            candidates = query.order_by(MatchCandidate.target_ref, MatchCandidate.rank).offset(skip).limit(limit).all()

    return {
        "total": total_count,
        "items": candidates,
        "skip": skip,
        "limit": limit
    }

@router.post("/candidates/bulk-decision")
async def submit_bulk_candidate_decision(
    req: BulkDecisionRequest,
    db: Session = Depends(get_db)
):
    if not req.candidate_ids:
        raise HTTPException(status_code=400, detail="candidate_ids tidak boleh kosong")
    if req.is_accepted not in (0, 1):
        raise HTTPException(status_code=422, detail="is_accepted hanya boleh 0 atau 1")

    updated_count = db.query(MatchCandidate).filter(
        MatchCandidate.id.in_(req.candidate_ids)
    ).update({"is_accepted": req.is_accepted})

    db.commit()
    return {
        "message": "Keputusan massal berhasil disimpan",
        "updated_count": updated_count,
        "is_accepted": req.is_accepted
    }

@router.post("/candidates/{candidate_id}/decision")
async def submit_candidate_decision(
    candidate_id: int,
    req: DecisionRequest,
    db: Session = Depends(get_db)
):
    cand = db.query(MatchCandidate).filter(MatchCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Kandidat tidak ditemukan")

    cand.is_accepted = req.is_accepted
    db.commit()
    return {"message": "Keputusan berhasil disimpan", "candidate_id": candidate_id, "is_accepted": cand.is_accepted}

@router.post("/{process_id}/finalize-review")
async def finalize_review(process_id: int, db: Session = Depends(get_db)):
    process = db.query(ReconciliationProcess).filter(ReconciliationProcess.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="Proses tidak ditemukan")
    if process.review_status == ReviewStatus.FINALIZED:
        return {"message": "Review sudah final", "review_status": process.review_status, "already_finalized": True}
    process.review_status = ReviewStatus.FINALIZED
    db.commit()
    return {"message": "Review finalisasi berhasil", "review_status": process.review_status, "already_finalized": False}
