"""Explicit mutations for radius analysis; GET requests only restore saved state."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.correction import CorrectionAttempt, CorrectionCheck, utc_now
from app.models.matching import ReconciliationProcess
from app.models.master_sisa import MasterSnapshot, CorrectionObservationCatalog
from app.models.radius_analysis import RadiusAnalysis
from app.models.upload import UploadBatch
from app.modules.corrections.service import CorrectionKind
from app.modules.corrections.empty_rules import TARGET_POLICY_KEY
from app.modules.corrections.radius_analysis import analysis_info, advance_analysis, automatic_review, create_analysis, get_analysis
from app.modules.corrections.empty_jobs import control_job, workflow_info

async def verify_category(request: Request, kind: CorrectionKind, db: Session = Depends(get_db)) -> None:
    """Validate the category before any analysis read or mutation."""
    analysis_id = request.path_params.get("analysis_id")
    batch_id = request.query_params.get("batch_id")
    if analysis_id is not None:
        try:
            identity = int(analysis_id)
        except (TypeError, ValueError):
            return  # The endpoint's parameter validation supplies HTTP 422.
        item = get_analysis(db, identity)
        batch_id = item.batch_id
    elif request.method == "POST":
        try:
            payload = await request.json()
        except ValueError:
            return
        batch_id = payload.get("batch_id") if isinstance(payload, dict) else None
    if batch_id is not None:
        try:
            identity = int(batch_id)
        except (TypeError, ValueError):
            return
        batch = db.get(UploadBatch, identity)
        if batch is None or batch.dataset_type.value != kind.value:
            raise HTTPException(404, "Unggahan atau analisis tidak sesuai kategori")


router = APIRouter(prefix="/{kind}/radius-analyses", dependencies=[Depends(verify_category)])


class StartAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: int = Field(gt=0)
    pdpj_review_id: int | None = Field(default=None, gt=0)
    actor: str = Field(min_length=1, max_length=80)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("actor")
    @classmethod
    def actor_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Isi nama petugas")
        return value.strip()


class StepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)


class StateRequest(StepRequest):
    state: Literal["running", "paused"]


class RadiusRequest(StepRequest):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    radius_meters: float = Field(gt=0, le=100000)


class SearchRequest(StepRequest):
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["running", "paused"]


class SearchJobRequest(JobRequest):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    radius_meters: float | None = Field(default=None, gt=0, le=100000)
    request_key: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


@router.get("")
def latest(batch_id: int = Query(gt=0), db: Session = Depends(get_db)):
    item = db.query(RadiusAnalysis).filter_by(batch_id=batch_id).order_by(RadiusAnalysis.id.desc()).first()
    return analysis_info(db, item) if item else None


@router.post("")
def start(req: StartAnalysis, db: Session = Depends(get_db)):
    previous = db.query(RadiusAnalysis).filter_by(request_key=req.request_key).first()
    review_id = req.pdpj_review_id or (previous.pdpj_review_id if previous else automatic_review(db).id)
    return analysis_info(db, create_analysis(db, req.batch_id, review_id, req.actor, req.request_key))


@router.get("/workflow")
def restore_workflow(batch_id: int = Query(gt=0), radius_meters: float | None = Query(None, gt=0, le=100000, allow_inf_nan=False), db: Session = Depends(get_db), analysis_id: Annotated[int | None, Query(gt=0)] = None):
    query = db.query(RadiusAnalysis).filter_by(batch_id=batch_id)
    if analysis_id is not None:
        query = query.filter_by(id=analysis_id)
    item = query.order_by(RadiusAnalysis.id.desc()).first()
    if analysis_id is not None and item is None:
        raise HTTPException(404, "Analisis tidak sesuai dengan unggahan ini")
    return workflow_info(db, item, radius_meters) if item else None


@router.post("/{analysis_id}/analysis-job")
def analysis_job(analysis_id: int, req: JobRequest, db: Session = Depends(get_db)):
    return control_job(db, analysis_id, "analysis", req.state)


@router.get("/{analysis_id}")
def status(analysis_id: int, radius_meters: float | None = Query(None, gt=0, le=100000, allow_inf_nan=False), db: Session = Depends(get_db)):
    return analysis_info(db, get_analysis(db, analysis_id), radius_meters)


@router.post("/{analysis_id}/advance")
def advance(analysis_id: int, req: StepRequest, db: Session = Depends(get_db)):
    return analysis_info(db, advance_analysis(db, analysis_id, req.revision))


@router.post("/{analysis_id}/state")
def control(analysis_id: int, req: StateRequest, db: Session = Depends(get_db)):
    item = get_analysis(db, analysis_id, locked=True)
    if item.revision != req.revision:
        raise HTTPException(409, "Progres berubah. Muat ulang analisis")
    if item.state != "ready":
        item.state, item.error = req.state, None
        item.revision += 1
        item.updated_at = utc_now()
        db.commit()
    return analysis_info(db, item)


@router.put("/{analysis_id}/radius")
def save_radius(analysis_id: int, req: RadiusRequest, db: Session = Depends(get_db)):
    item = get_analysis(db, analysis_id, locked=True)
    if item.revision != req.revision or item.state != "ready":
        raise HTTPException(409, "Selesaikan dan muat ulang analisis terlebih dahulu")
    if item.progress.get("search_process_id"):
        raise HTTPException(409, "Pencarian sudah dibuat dengan radius tersimpan. Buka proses tersebut untuk melanjutkan")
    item.progress = {**item.progress, "selected_radius_meters": req.radius_meters}
    item.revision += 1
    item.updated_at = utc_now()
    db.commit()
    return analysis_info(db, item, req.radius_meters)


@router.post("/{analysis_id}/search")
def search(analysis_id: int, req: SearchRequest, db: Session = Depends(get_db)):
    from app.modules.corrections.progress import initialize_progress
    from app.modules.corrections.service import reserve_run
    from app.modules.pdpj.service import completed_review
    from app.models.pdpj import PdpjReview

    item = get_analysis(db, analysis_id, locked=True)
    radius = item.progress.get("selected_radius_meters")
    if item.state != "ready" or radius is None:
        raise HTTPException(409, "Selesaikan analisis dan simpan radius terlebih dahulu")
    previous = db.query(CorrectionAttempt).filter_by(request_key=req.request_key).first()
    if previous:
        if item.progress.get("search_process_id") != previous.process_id:
            raise HTTPException(409, "Permintaan sudah digunakan untuk pemeriksaan lain")
        return {"process_id": previous.process_id, "batch_id": item.batch_id}
    if item.revision != req.revision:
        raise HTTPException(409, "Pengaturan berubah. Muat ulang analisis")
    if item.progress.get("search_process_id"):
        return {"process_id": item.progress["search_process_id"], "batch_id": item.batch_id}
    review = db.get(PdpjReview, item.pdpj_review_id)
    assert review is not None
    try:
        completed_review(db, review.batch_id, review.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    prepared = db.get(ReconciliationProcess, item.process_id)
    assert prepared is not None
    snapshot = db.get(MasterSnapshot, prepared.master_snapshot_id) if prepared.master_snapshot_id else None
    catalog = db.get(CorrectionObservationCatalog, prepared.master_snapshot_id) if prepared.master_snapshot_id else None
    if snapshot is None or not snapshot.ready or catalog is None or not catalog.processing.get("ready"):
        raise HTTPException(409, "Master dan indeks koordinat belum siap; selesaikan analisis terlebih dahulu")
    category = db.get(UploadBatch, item.batch_id).dataset_type.value
    process = ReconciliationProcess(process_name=f"Koreksi {category.replace('_', ' ').upper()}", target_batch_id=item.batch_id, source_batches=prepared.source_batches, master_snapshot_id=prepared.master_snapshot_id, radius_meters=radius)
    db.add(process)
    db.flush()
    db.add(CorrectionCheck(process_id=process.id, category=category, pdpj_review_id=item.pdpj_review_id))
    db.flush()
    run = reserve_run(db, process, req.request_key, item.actor, radius)
    initialize_progress(db, process, run)
    # Reuse exactly the prepared eligible observations. No second exclusion or
    # source selection pass when the operator chooses the search radius.
    run.processing = {**run.processing, "stage": "matching", "radius_analysis_id": item.id,
                      "coordinate_rows": 0, "no_candidate_rows": 0, "other_issue_rows": 0, "idpel_in_pdpj_rows": 0, TARGET_POLICY_KEY: item.progress.get(TARGET_POLICY_KEY)}
    item.progress = {**item.progress, "search_process_id": process.id}
    item.revision += 1
    db.commit()
    return {"process_id": process.id, "batch_id": item.batch_id}


@router.post("/{analysis_id}/search-job")
def search_job(analysis_id: int, req: SearchJobRequest, db: Session = Depends(get_db)):
    if req.state == "paused":
        # Signal pause before taking SQLite's writer lock; the active row owns
        # that lock until it commits, and must see the signal before the next row.
        return control_job(db, analysis_id, "search", "paused")
    item = get_analysis(db, analysis_id)
    if not item.progress.get("search_process_id"):
        item = get_analysis(db, analysis_id, locked=True)
    if not item.progress.get("search_process_id"):
        if req.state != "running" or req.radius_meters is None or req.request_key is None:
            raise HTTPException(422, "Isi radius dan kunci permintaan untuk memulai pencarian")
        save_radius(analysis_id, RadiusRequest(revision=item.revision, radius_meters=req.radius_meters), db)
        search(analysis_id, SearchRequest(revision=item.revision, request_key=req.request_key), db)
    elif req.radius_meters is not None and req.radius_meters != item.progress.get("selected_radius_meters"):
        raise HTTPException(409, "Pencarian sudah memakai radius tersimpan; lanjutkan proses yang sama")
    db.commit()
    return control_job(db, analysis_id, "search", req.state)
