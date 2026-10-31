"""Categorized imports, real processing status, complete summaries, and stored candidate details."""

import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, load_only, object_session

from app.config import settings
from app.database import get_db
from app.models.correction import (
    CorrectionCandidateEvidence,
    CorrectionCheck,
    CorrectionTarget,
)
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ReconciliationProcess,
)
from app.models.pdpj import PdpjReview
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.corrections.decisions import router as decisions_router
from app.modules.corrections.map_summary import radius_summary
from app.modules.corrections.pdpj_updates import pdpj_update_info
from app.modules.corrections.progress import advance_progress, control_progress
from app.modules.corrections.results import router as results_router
from app.modules.corrections.service import (
    CorrectionKind,
    check_process,
    create_check,
    retry_check,
    selected_run,
    source_batch,
)
from app.modules.master.router import batch_info
from app.modules.spatial.pipeline import execute_pipeline
from app.modules.upload.normalization import (
    NORMALIZATION_VERSION,
    extract_standard_fields,
    validate_fields,
)
from app.modules.upload.pagination import load_original_cells, source_page_ids
from app.modules.upload.storage import database_write_error
from app.processing_activity import monitor_request, request_activity
from app.tasks.spatial_tasks import (
    execute_batch_reconciliation_pipeline,
    mark_process_failed,
)

DbSession = Annotated[Session, Depends(get_db)]
router = APIRouter(prefix="/corrections", tags=["Data Koreksi"])
logger = logging.getLogger(__name__)
RecordFilter = Literal[
    "all",
    "not_checked",
    "pdpj_conflict",
    "invalid_data",
    "incomplete_coordinates",
    "matched",
    "no_candidates",
    "identity_found",
    "identity_not_found",
]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    radius_meters: float = Field(100, gt=0, le=100000)
    actor: str = Field(min_length=1, max_length=80)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    incremental: bool = False

    @field_validator("actor")
    @classmethod
    def validate_actor(cls, value: str) -> str:
        """Store a nonempty operator label without claiming authenticated identity."""
        if not value.strip():
            raise ValueError("Nama petugas wajib diisi")
        return value.strip()


class StartCheck(SearchRequest):
    batch_id: int = Field(gt=0)
    pdpj_review_id: int = Field(gt=0)


class RetryCheck(SearchRequest):
    latest_run_id: int = Field(gt=0)


class ProgressControl(BaseModel):
    run_id: int = Field(gt=0)


class ProgressStep(ProgressControl):
    revision: int = Field(ge=1)
    chunk_size: int = Field(100, ge=1, le=400)


def run_info(run: MatchingRun) -> dict[str, Any]:
    """Expose actual state of each immutable search attempt."""
    return {
        "id": run.id,
        "generation": run.generation,
        "candidate_policy": run.candidate_policy,
        "status": run.status.value,
        "failure_code": run.failure_code,
        "radius_meters": run.radius_meters,
        "total_targets": run.total_targets,
        "matched_targets": run.matched_targets,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "processing": run.processing,
        "activity": request_activity(object_session(run), "correction", run.id),
    }


def check_info(
    db: Session,
    kind: CorrectionKind,
    process_id: int,
    include_update_conflicts: bool = True,
) -> dict[str, Any]:
    """Keep the latest job state separate from the last published generation."""
    check, process = check_process(db, kind, process_id)
    runs = (
        db.query(MatchingRun)
        .filter(MatchingRun.process_id == process_id)
        .order_by(MatchingRun.generation.desc())
        .all()
    )
    return {
        "process_id": process.id,
        "batch_id": process.target_batch_id,
        "category": check.category,
        "pdpj_review_id": check.pdpj_review_id,
        "pdpj_update": pdpj_update_info(
            db, process_id, check.pdpj_review_id, include_update_conflicts
        ),
        "status": process.matching_status.value,
        "current_generation": process.current_generation,
        "master_snapshot_id": process.master_snapshot_id,
        "source_batches": process.source_batches,
        "latest_run": run_info(runs[0]) if runs else None,
        "runs": [run_info(run) for run in runs],
    }


def dispatch(
    db: Session, process: ReconciliationProcess, run: MatchingRun, fresh: bool
) -> str:
    """Persist failure or completion; never manufacture a successful popup in the UI."""
    if not fresh:
        return "existing"
    process_id, run_id = process.id, run.id
    try:
        execute_batch_reconciliation_pipeline.apply_async(
            kwargs={
                "process_id": process_id,
                "run_id": run_id,
                "retry_on_failure": False,
            },
            retry=False,
            ignore_result=True,
        )
        return "async_celery"
    except Exception as exc:  # noqa: BLE001 -- Submission failures must become a visible job state.
        logger.warning(
            "Antrean koreksi tidak tersedia untuk proses #%s (%s)",
            process_id,
            type(exc).__name__,
        )
        if not settings.ALLOW_SYNC_FALLBACK:
            mark_process_failed(
                db, process_id, run_id, failure_code="worker_unavailable"
            )
            return "worker_unavailable"
    try:
        execute_pipeline(db, process_id, run_id)
        return "sync_fallback"
    except Exception as exc:  # noqa: BLE001 -- Roll back every failed search before publishing failure.
        logger.error(
            "Koreksi gagal untuk proses #%s (%s)", process_id, type(exc).__name__
        )
        mark_process_failed(db, process_id, run_id)
        return "failed"


def record_scope(
    db: Session,
    kind: CorrectionKind,
    batch_id: int | None,
    process_id: int | None,
    generation: int | None,
) -> tuple[Any, MatchingRun | None]:
    """Build one category/batch/run query without falling back to another process."""
    if batch_id is not None:
        source_batch(db, kind, batch_id)
    run = None
    if process_id is not None:
        _, process = check_process(db, kind, process_id)
        if batch_id is not None and process.target_batch_id != batch_id:
            raise HTTPException(
                404, "Pemeriksaan tidak menggunakan berkas yang dipilih"
            )
        batch_id = process.target_batch_id
        run = selected_run(db, process, generation, include_partial=True)
    elif generation is not None:
        raise HTTPException(422, "Pilih pemeriksaan untuk melihat versi pencarian")
    query = (
        db.query(SourceRecord, UploadBatch, CorrectionTarget)
        .options(
            load_only(
                SourceRecord.id,
                SourceRecord.batch_id,
                SourceRecord.row_number,
                SourceRecord.normalized_data,
                SourceRecord.is_valid,
                SourceRecord.validation_errors,
            )
        )
        .join(UploadBatch, SourceRecord.batch_id == UploadBatch.id)
        .outerjoin(
            CorrectionTarget,
            and_(
                CorrectionTarget.source_record_id == SourceRecord.id,
                CorrectionTarget.run_id == run.id,
            )
            if run
            else CorrectionTarget.id == -1,
        )
        .filter(
            UploadBatch.dataset_type == DatasetType(kind.value),
            UploadBatch.status == BatchStatus.COMPLETED,
        )
    )
    if batch_id is not None:
        query = query.filter(SourceRecord.batch_id == batch_id)
    return query, run


def cached_preview_fields(
    record: SourceRecord, batch: UploadBatch
) -> dict[str, Any] | None:
    """Reuse only a current, valid normalization; preserve raw parsing of errors."""
    if (
        batch.catalog_version == NORMALIZATION_VERSION
        and record.normalized_data
        and record.normalized_data.get("_normalization_version")
        == NORMALIZATION_VERSION
        and record.is_valid
        and not record.validation_errors
    ):
        return record.normalized_data
    return None


def record_info(
    record: SourceRecord, batch: UploadBatch, outcome: CorrectionTarget | None
) -> dict[str, Any]:
    """Return every source row even when it has no coordinates or candidates."""
    cached = cached_preview_fields(record, batch) if not outcome else None
    fields = (
        outcome.fields
        if outcome
        else {**cached, "validation_errors": []}
        if cached is not None
        else extract_standard_fields(record.data or {}, batch.column_mapping)
    )
    return {
        "id": record.id,
        "batch_id": batch.id,
        "category": batch.dataset_type.value,
        "row_number": record.row_number,
        "filename": batch.filename,
        "source_sheet": batch.source_sheet,
        "fields": fields,
        "identity_status": outcome.identity_status if outcome else "not_checked",
        "search_status": outcome.search_status if outcome else "not_checked",
        "candidate_count": outcome.candidate_count if outcome else 0,
        "errors": outcome.errors
        if outcome
        else validate_fields(fields, batch.dataset_type),
        "conflicts": outcome.conflicts if outcome else [],
        "warnings": outcome.warnings if outcome else [],
    }


@router.get("/ready-pdpj")
def ready_pdpj(db: DbSession) -> list[dict[str, Any]]:
    """Offer approved versions of each file's latest working review."""
    latest: dict[int, PdpjReview] = {}
    for review in (
        db.query(PdpjReview)
        .filter(PdpjReview.source_review_id.is_(None))
        .order_by(PdpjReview.id.desc())
        .all()
    ):
        latest.setdefault(review.batch_id, review)
    approved: list[PdpjReview] = []
    for review in latest.values():
        if review.status == "completed":
            approved.append(review)
        approved.extend(
            db.query(PdpjReview)
            .filter(
                PdpjReview.source_review_id == review.id,
                PdpjReview.status == "completed",
            )
            .order_by(PdpjReview.id.desc())
            .all()
        )
    return [
        {
            "review_id": review.id,
            "batch_id": batch.id,
            "filename": batch.filename,
            "completed_by": review.completed_by,
            "completed_at": review.completed_at,
            "master_batch_ids": review.master_batch_ids,
            "source_review_id": review.source_review_id,
            "publication": review.publication,
        }
        for review in approved
        if (batch := db.get(UploadBatch, review.batch_id)) is not None
    ]


@router.get("/{kind}/batches")
def list_batches(kind: CorrectionKind, db: DbSession) -> list[dict[str, Any]]:
    """Do not guess the category of legacy target uploads."""
    return [
        batch_info(batch)
        for batch in db.query(UploadBatch)
        .filter(UploadBatch.dataset_type == DatasetType(kind.value))
        .order_by(UploadBatch.id.desc())
        .all()
    ]


@router.get("/{kind}/batches/{batch_id}")
def batch_preview(kind: CorrectionKind, batch_id: int, db: DbSession) -> dict[str, Any]:
    """Resume column mapping without creating a duplicate upload."""
    batch = source_batch(db, kind, batch_id)
    rows = (
        db.query(SourceRecord)
        .filter(SourceRecord.batch_id == batch.id)
        .order_by(SourceRecord.id)
        .limit(5)
        .all()
    )
    return {
        **batch_info(batch),
        "headers": list((rows[0].data or {}).keys()) if rows else [],
        "preview": [row.data for row in rows],
        "row_numbers": [row.row_number for row in rows],
        "column_mapping": batch.column_mapping or {},
    }


@router.get("/{kind}/checks")
def list_checks(
    kind: CorrectionKind,
    db: DbSession,
    batch_id: int = Query(gt=0),
    include_update_conflicts: bool = True,
) -> list[dict[str, Any]]:
    """List previous checks with their original PDPJ source and parameters."""
    source_batch(db, kind, batch_id)
    processes = (
        db.query(ReconciliationProcess.id)
        .join(CorrectionCheck, CorrectionCheck.process_id == ReconciliationProcess.id)
        .filter(
            CorrectionCheck.category == kind.value,
            ReconciliationProcess.target_batch_id == batch_id,
        )
        .order_by(ReconciliationProcess.id.desc())
        .all()
    )
    return [
        check_info(db, kind, value, include_update_conflicts) for (value,) in processes
    ]


@router.post("/{kind}/checks")
def start_check(kind: CorrectionKind, req: StartCheck, db: DbSession) -> dict[str, Any]:
    """Check category ownership and completed PDPJ before submitting real work."""
    process, run, fresh = create_check(
        db,
        kind,
        req.batch_id,
        req.pdpj_review_id,
        req.radius_meters,
        req.request_key,
        req.actor,
        req.incremental,
    )
    run_id, process_id = run.id, process.id
    mode = "incremental" if run.processing else dispatch(db, process, run, fresh)
    return {
        **check_info(db, kind, process_id),
        "requested_run_id": run_id,
        "execution_mode": mode,
    }


@router.get("/{kind}/checks/{process_id}")
def get_check(
    kind: CorrectionKind,
    process_id: int,
    db: DbSession,
    include_update_conflicts: bool = True,
) -> dict[str, Any]:
    """Poll status until the requested attempt has actually completed."""
    return check_info(db, kind, process_id, include_update_conflicts)


@router.get("/{kind}/checks/{process_id}/pdpj-update")
def get_pdpj_update(
    kind: CorrectionKind, process_id: int, db: DbSession
) -> dict[str, Any] | None:
    """Review conflicts independently of the lightweight process restoration path."""
    check, _ = check_process(db, kind, process_id)
    return pdpj_update_info(db, process_id, check.pdpj_review_id)


@router.post("/{kind}/checks/{process_id}/retry")
def rerun_check(
    kind: CorrectionKind, process_id: int, req: RetryCheck, db: DbSession
) -> dict[str, Any]:
    """Retain earlier candidates and row outcomes when changing radius or retrying failure."""
    process, run, fresh = retry_check(
        db,
        kind,
        process_id,
        req.latest_run_id,
        req.radius_meters,
        req.request_key,
        req.actor,
        req.incremental,
    )
    run_id = run.id
    mode = "incremental" if run.processing else dispatch(db, process, run, fresh)
    return {
        **check_info(db, kind, process_id),
        "requested_run_id": run_id,
        "execution_mode": mode,
    }


@router.get("/{kind}/checks/{process_id}/progress")
def processing_status(
    kind: CorrectionKind, process_id: int, db: DbSession
) -> dict[str, Any]:
    check_process(db, kind, process_id)
    run = (
        db.query(MatchingRun)
        .filter_by(process_id=process_id)
        .order_by(MatchingRun.generation.desc())
        .first()
    )
    if run is None:
        raise HTTPException(404, "Pemeriksaan tidak ditemukan")
    return run_info(run)


@router.post("/{kind}/checks/{process_id}/advance")
@monitor_request("correction", "req.run_id", "matching")
def advance_check(
    kind: CorrectionKind, process_id: int, req: ProgressStep, db: DbSession
) -> dict[str, Any]:
    try:
        return run_info(
            advance_progress(
                db, kind, process_id, req.run_id, req.revision, req.chunk_size
            )
        )
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "pemrosesan koreksi") from exc


@router.post("/{kind}/checks/{process_id}/pause")
@monitor_request("correction", "req.run_id", "pausing")
def pause_check(
    kind: CorrectionKind, process_id: int, req: ProgressControl, db: DbSession
) -> dict[str, Any]:
    try:
        return run_info(control_progress(db, kind, process_id, req.run_id, "paused"))
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "jeda koreksi") from exc


@router.post("/{kind}/checks/{process_id}/resume")
@monitor_request("correction", "req.run_id", "resuming")
def resume_check(
    kind: CorrectionKind, process_id: int, req: ProgressControl, db: DbSession
) -> dict[str, Any]:
    try:
        return run_info(control_progress(db, kind, process_id, req.run_id, "running"))
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "kelanjutan koreksi") from exc


@router.get("/{kind}/map-summary")
def map_summary(
    kind: CorrectionKind,
    db: DbSession,
    process_id: int = Query(gt=0),
    generation: int | None = Query(None, ge=1),
    radius_meters: float = Query(gt=0, le=100000, allow_inf_nan=False),
) -> dict[str, Any]:
    """Read radius-specific counts and target statuses from persisted candidates."""
    return radius_summary(db, kind, process_id, generation, radius_meters)


@router.get("/{kind}/summary")
def summary(
    kind: CorrectionKind,
    db: DbSession,
    batch_id: int | None = Query(None, gt=0),
    process_id: int | None = Query(None, gt=0),
    generation: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    """Count unique source rows over the whole scope, independent of table pagination."""
    query, run = record_scope(db, kind, batch_id, process_id, generation)
    total = query.count()
    counts = dict(
        query.with_entities(CorrectionTarget.search_status, func.count(SourceRecord.id))
        .group_by(CorrectionTarget.search_status)
        .all()
    )
    incomplete = query.filter(
        or_(
            SourceRecord.normalized_data["lat"].as_float().is_(None),
            SourceRecord.normalized_data["lon"].as_float().is_(None),
        )
    ).count()
    return {
        "category": kind.value,
        "process_id": process_id,
        "generation": run.generation if run else None,
        "total_rows": total,
        "not_checked": counts.get(None, 0),
        "pdpj_conflicts": counts.get("pdpj_conflict", 0),
        "matched": counts.get("matched", 0),
        "no_candidates": counts.get("no_candidates", 0),
        "invalid_data": counts.get("invalid_data", 0),
        "incomplete_coordinates": incomplete,
        "identity_found": query.filter(
            CorrectionTarget.identity_status == "found"
        ).count(),
        "identity_not_found": query.filter(
            CorrectionTarget.identity_status == "not_found"
        ).count(),
        "eligible_searched": counts.get("matched", 0) + counts.get("no_candidates", 0),
    }


@router.get("/{kind}/records")
def list_records(
    kind: CorrectionKind,
    db: DbSession,
    batch_id: int | None = Query(None, gt=0),
    process_id: int | None = Query(None, gt=0),
    generation: int | None = Query(None, ge=1),
    q: str = Query("", max_length=120),
    status: RecordFilter = "all",
    saved_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Filter rows, rather than candidate records, so no-result targets remain visible."""
    query, run = record_scope(db, kind, batch_id, process_id, generation)
    payload_query = query
    if saved_only:
        query = query.filter(CorrectionTarget.id.is_not(None))
    if q.strip():
        pattern = (
            "%"
            + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        query = query.filter(
            or_(
                *(
                    SourceRecord.normalized_data[key]
                    .as_string()
                    .ilike(pattern, escape="\\")
                    for key in (
                        "idpel",
                        "nama",
                        "target_ref",
                        "meter_ref",
                        "agenda_ref",
                        "survey_ref",
                    )
                )
            )
        )
    if status == "not_checked":
        query = query.filter(CorrectionTarget.id.is_(None))
    elif status in {"identity_found", "identity_not_found"}:
        query = query.filter(
            CorrectionTarget.identity_status
            == ("found" if status == "identity_found" else "not_found")
        )
    elif status == "incomplete_coordinates":
        query = query.filter(
            or_(
                SourceRecord.normalized_data["lat"].as_float().is_(None),
                SourceRecord.normalized_data["lon"].as_float().is_(None),
            )
        )
    elif status != "all":
        query = query.filter(CorrectionTarget.search_status == status)
    selected_batch = batch_id
    if run is not None:
        selected_process = db.get(ReconciliationProcess, run.process_id)
        assert selected_process is not None
        selected_batch = selected_process.target_batch_id
    batches = db.query(UploadBatch).filter(
        UploadBatch.dataset_type == DatasetType(kind.value),
        UploadBatch.status == BatchStatus.COMPLETED,
    )
    if selected_batch is not None:
        batches = batches.filter(UploadBatch.id == selected_batch)
    selected_batches = batches.all()
    total, identities = source_page_ids(
        db,
        query,
        [batch.id for batch in selected_batches],
        skip,
        limit,
        unfiltered=not q.strip() and status == "all" and not saved_only,
        known_totals={batch.id: batch.total_rows for batch in selected_batches},
    )
    records = (
        payload_query.filter(SourceRecord.id.in_(identities))
        .order_by(SourceRecord.batch_id.desc(), SourceRecord.id)
        .all()
        if identities
        else []
    )
    load_original_cells(
        db,
        [
            record.id
            for record, batch, outcome in records
            if outcome is None and cached_preview_fields(record, batch) is None
        ],
    )
    return {
        "total": total,
        "items": [
            record_info(record, batch, outcome) for record, batch, outcome in records
        ],
    }


@router.get("/{kind}/records/{record_id}")
def record_detail(
    kind: CorrectionKind,
    record_id: int,
    db: DbSession,
    process_id: int | None = Query(None, gt=0),
    generation: int | None = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    radius_meters: float | None = Query(None, gt=0, le=100000, allow_inf_nan=False),
) -> dict[str, Any]:
    """Read candidate snapshots only; inspecting a row must not reload the master."""
    record = db.get(SourceRecord, record_id)
    if record is None:
        raise HTTPException(404, "Baris koreksi tidak ditemukan")
    source_batch(db, kind, record.batch_id)
    query, run = record_scope(db, kind, record.batch_id, process_id, generation)
    result = query.filter(SourceRecord.id == record_id).first()
    if result is None:
        raise HTTPException(404, "Selesaikan mapping berkas koreksi terlebih dahulu")
    record, batch, outcome = result
    candidates = (
        db.query(MatchCandidate, CorrectionCandidateEvidence)
        .join(
            CorrectionCandidateEvidence,
            CorrectionCandidateEvidence.candidate_id == MatchCandidate.id,
        )
        .filter(
            MatchCandidate.process_id == process_id,
            MatchCandidate.generation == (run.generation if run else -1),
            MatchCandidate.target_record_id == record_id,
        )
    )
    if radius_meters is not None:
        if run is None or radius_meters > run.radius_meters:
            raise HTTPException(
                409, "Perluas pemeriksaan terlebih dahulu untuk radius ini"
            )
        candidates = candidates.filter(MatchCandidate.distance_meters <= radius_meters)
    return {
        **record_info(record, batch, outcome),
        "raw_data": record.data,
        "column_mapping": batch.column_mapping or {},
        "generation": run.generation if run else None,
        "radius_meters": run.radius_meters if run else None,
        "candidates_total": candidates.count(),
        "candidates": [
            {
                "id": candidate.id,
                "rank": candidate.rank,
                "distance_meters": candidate.distance_meters,
                "fields": evidence.fields,
                "observations": evidence.observations,
                "is_accepted": candidate.is_accepted,
            }
            for candidate, evidence in candidates.order_by(MatchCandidate.rank)
            .offset(skip)
            .limit(limit)
            .all()
        ],
    }


router.include_router(decisions_router)
router.include_router(results_router)
