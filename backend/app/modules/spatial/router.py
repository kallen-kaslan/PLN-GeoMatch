from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.modules.spatial.master_builder import build_combined_master
from app.modules.spatial.preparation import process_master_sisa_exclusion
from app.modules.spatial.engine import run_spatial_matching_job
from app.models.matching import MatchCandidate, ReconciliationProcess, ReviewStatus

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
    """
    try:
        return run_spatial_matching_job(
            db=db,
            process_name=req.process_name,
            target_batch_id=req.target_batch_id,
            radius_meters=req.radius_meters,
            max_candidates_per_target=req.max_candidates
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{process_id}/candidates")
async def get_candidates(
    process_id: int,
    db: Session = Depends(get_db),
    status_filter: Optional[int] = Query(None)
):
    query = db.query(MatchCandidate).filter(MatchCandidate.process_id == process_id)
    if status_filter is not None:
        query = query.filter(MatchCandidate.is_accepted == status_filter)

    candidates = query.order_by(MatchCandidate.target_ref, MatchCandidate.rank).all()

    # Fallback: jika process_id spesifik tidak ada kandidat, cari proses yang ada datanya
    if not candidates:
        latest_with_data = (
            db.query(ReconciliationProcess)
            .join(MatchCandidate, MatchCandidate.process_id == ReconciliationProcess.id)
            .order_by(ReconciliationProcess.id.desc())
            .first()
        )
        if latest_with_data and latest_with_data.id != process_id:
            query = db.query(MatchCandidate).filter(MatchCandidate.process_id == latest_with_data.id)
            if status_filter is not None:
                query = query.filter(MatchCandidate.is_accepted == status_filter)
            candidates = query.order_by(MatchCandidate.target_ref, MatchCandidate.rank).all()

    return candidates

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
