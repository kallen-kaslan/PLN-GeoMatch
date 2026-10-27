"""PDPJ import catalogue, identity validation, recommendations, and audited corrections."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.pdpj import PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow
from app.models.upload import DatasetType, SourceRecord, UploadBatch
from app.modules.master.router import batch_info
from app.modules.pdpj.service import (
    advance_review,
    before_change,
    complete_validation,
    control_processing,
    create_review,
    get_review,
    pdpj_batch,
    record_change,
    refresh_rows,
    update_fields,
)
from app.modules.upload.storage import database_write_error
from app.pdpj_warning_schema import DUPLICATE_IDPEL

DbSession = Annotated[Session, Depends(get_db)]
router = APIRouter(prefix="/pdpj", tags=["Validasi PDPJ"])


class StartReview(BaseModel):
    batch_id: int = Field(gt=0)
    master_batch_ids: list[int] | None = Field(None, max_length=1000)
    incremental: bool = False


class ProcessingStep(BaseModel):
    revision: int = Field(ge=1)


class ReviewAction(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=80)

    @field_validator("actor")
    @classmethod
    def actor_not_blank(cls, value: str) -> str:
        """Store an explicit operator label while authentication remains a scaffold."""
        if not value.strip():
            raise ValueError("Nama petugas wajib diisi")
        return value.strip()


class EditRow(ReviewAction):
    fields: dict[str, str | float | int | None]
    reason: str = Field("", max_length=1000)


class ApplyRecommendation(ReviewAction):
    recommendation_id: int = Field(gt=0)
    fields: list[str] = Field(min_length=1, max_length=40)
    overwrite: bool = False
    reason: str = Field("", max_length=1000)


class DecideRow(ReviewAction):
    action: Literal["reviewed", "exception", "reopen"]
    reason: str = Field("", max_length=1000)


class CompleteWithExceptions(ReviewAction):
    reason: str = Field(min_length=1, max_length=1000)
    expected_unresolved: int = Field(gt=0)
    confirmed: Literal[True]

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Alasan pengecualian massal wajib diisi")
        return value.strip()


def review_info(review: PdpjReview) -> dict[str, Any]:
    """Expose stable review identity and optimistic concurrency revision."""
    return {
        "id": review.id,
        "batch_id": review.batch_id,
        "master_batch_ids": review.master_batch_ids,
        "status": review.status,
        "revision": review.revision,
        "created_at": review.created_at,
        "completed_at": review.completed_at,
        "completed_by": review.completed_by,
        "processing": review.processing,
    }


def row_info(row: PdpjRow) -> dict[str, Any]:
    """Return current values and independent identity, completeness, and review states."""
    warnings = list(row.warnings or [])
    if not any(item.get("code") == DUPLICATE_IDPEL for item in warnings):
        warnings.extend(
            item for item in row.issues if item.get("code") == DUPLICATE_IDPEL
        )
    return {
        "id": row.id,
        "source_record_id": row.source_record_id,
        "row_number": row.row_number,
        "fields": row.current_fields,
        "existence": row.existence,
        "issues": [item for item in row.issues if item.get("code") != DUPLICATE_IDPEL],
        "warnings": warnings,
        "coordinates_complete": row.current_fields.get("lat") is not None
        and row.current_fields.get("lon") is not None,
        "recommendation_count": row.recommendation_count,
        "reviewed": row.reviewed,
        "exception": row.exception,
        "exception_reason": row.exception_reason,
    }


def selected_row(db: Session, review_id: int, row_id: int) -> PdpjRow:
    """Prevent row and review IDs from crossing validation versions."""
    row = (
        db.query(PdpjRow)
        .filter(PdpjRow.id == row_id, PdpjRow.review_id == review_id)
        .populate_existing()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Baris pada pemeriksaan ini tidak ditemukan")
    return row


@router.get("/batches")
def list_batches(db: DbSession) -> list[dict[str, Any]]:
    """List PDPJ uploads separately from masters and correction data."""
    return [
        batch_info(batch)
        for batch in db.query(UploadBatch)
        .filter(UploadBatch.dataset_type == DatasetType.PDPJ)
        .order_by(UploadBatch.id.desc())
        .all()
    ]


@router.get("/batches/{batch_id}")
def batch_preview(batch_id: int, db: DbSession) -> dict[str, Any]:
    """Resume mapping of an already uploaded PDPJ file."""
    batch = pdpj_batch(db, batch_id)
    rows = (
        db.query(SourceRecord)
        .filter(SourceRecord.batch_id == batch_id)
        .order_by(SourceRecord.id)
        .limit(5)
        .all()
    )
    return {
        **batch_info(batch),
        "column_mapping": batch.column_mapping or {},
        "headers": list((rows[0].data or {}).keys()) if rows else [],
        "preview": [row.data for row in rows],
        "row_numbers": [row.row_number for row in rows],
    }


@router.get("/batches/{batch_id}/reviews")
def list_reviews(batch_id: int, db: DbSession) -> list[dict[str, Any]]:
    """Retain completed checks when the operator starts a new validation version."""
    pdpj_batch(db, batch_id)
    return [
        review_info(review)
        for review in db.query(PdpjReview)
        .filter(PdpjReview.batch_id == batch_id)
        .order_by(PdpjReview.id.desc())
        .all()
    ]


@router.post("/reviews")
def start_review(req: StartReview, db: DbSession) -> dict[str, Any]:
    """Match every PDPJ identity against every observation in the selected sources."""
    if req.incremental:
        return review_info(
            create_review(db, req.batch_id, req.master_batch_ids, incremental=True)
        )
    return review_info(create_review(db, req.batch_id, req.master_batch_ids))


@router.post("/reviews/{review_id}/advance")
def advance_processing(
    review_id: int, req: ProcessingStep, db: DbSession
) -> dict[str, Any]:
    """Process one bounded transaction and return its durable checkpoint."""
    try:
        return review_info(advance_review(db, review_id, req.revision))
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "pemeriksaan PDPJ") from exc


@router.post("/reviews/{review_id}/pause")
def pause_processing(review_id: int, db: DbSession) -> dict[str, Any]:
    """Wait for the active chunk and preserve all committed results."""
    try:
        return review_info(control_processing(db, review_id, "paused"))
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "jeda pemeriksaan PDPJ") from exc


@router.post("/reviews/{review_id}/resume")
def resume_processing(review_id: int, db: DbSession) -> dict[str, Any]:
    """Continue with the saved sources and cursors, never create another review."""
    try:
        return review_info(control_processing(db, review_id, "running"))
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "kelanjutan pemeriksaan PDPJ") from exc


@router.get("/reviews/{review_id}")
def review_summary(review_id: int, db: DbSession) -> dict[str, Any]:
    """Aggregate the entire review, independent of row filters and pagination."""
    review = get_review(db, review_id)
    query = db.query(PdpjRow).filter(PdpjRow.review_id == review.id)
    unresolved = and_(
        func.json_array_length(PdpjRow.issues) > 0, PdpjRow.exception.is_(False)
    )
    total, found, not_found, empty, invalid, incomplete, exceptions, pending = (
        query.with_entities(
            func.count(PdpjRow.id),
            func.count(PdpjRow.id).filter(PdpjRow.existence == "found"),
            func.count(PdpjRow.id).filter(PdpjRow.existence == "not_found"),
            func.count(PdpjRow.id).filter(PdpjRow.existence == "empty"),
            func.count(PdpjRow.id).filter(PdpjRow.existence == "invalid"),
            func.count(PdpjRow.id).filter(
                or_(
                    PdpjRow.current_fields["lat"].as_float().is_(None),
                    PdpjRow.current_fields["lon"].as_float().is_(None),
                )
            ),
            func.count(PdpjRow.id).filter(PdpjRow.exception.is_(True)),
            func.count(PdpjRow.id).filter(unresolved),
        ).one()
    )
    return {
        **review_info(review),
        "summary": {
            "total_rows": total,
            "found": found,
            "not_found": not_found,
            "empty": empty,
            "invalid": invalid,
            "incomplete_coordinates": incomplete,
            "exceptions": exceptions,
            "unresolved": pending,
            "ready": total - pending - exceptions,
        },
        "masters": [
            batch_info(batch)
            for batch in db.query(UploadBatch)
            .filter(UploadBatch.id.in_(review.master_batch_ids))
            .order_by(UploadBatch.id)
            .all()
        ],
    }


@router.get("/reviews/{review_id}/rows")
def list_rows(
    review_id: int,
    db: DbSession,
    q: str = Query("", max_length=120),
    status: Literal[
        "all",
        "found",
        "not_found",
        "empty",
        "invalid",
        "incomplete",
        "unresolved",
        "exception",
        "ready",
    ] = "all",
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Include invalid and empty identities rather than silently discarding rows."""
    get_review(db, review_id)
    query = db.query(PdpjRow).filter(PdpjRow.review_id == review_id)
    if q.strip():
        pattern = (
            "%"
            + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        query = query.filter(
            or_(
                *(
                    PdpjRow.current_fields[key].as_string().ilike(pattern, escape="\\")
                    for key in ("idpel", "nama", "target_ref")
                )
            )
        )
    if status in {"found", "not_found", "empty", "invalid"}:
        query = query.filter(PdpjRow.existence == status)
    elif status == "incomplete":
        query = query.filter(
            or_(
                PdpjRow.current_fields["lat"].as_float().is_(None),
                PdpjRow.current_fields["lon"].as_float().is_(None),
            )
        )
    elif status == "unresolved":
        query = query.filter(
            func.json_array_length(PdpjRow.issues) > 0, PdpjRow.exception.is_(False)
        )
    elif status == "exception":
        query = query.filter(PdpjRow.exception.is_(True))
    elif status == "ready":
        query = query.filter(
            func.json_array_length(PdpjRow.issues) == 0, PdpjRow.exception.is_(False)
        )
    total = query.count()
    return {
        "total": total,
        "items": [
            row_info(row)
            for row in query.order_by(PdpjRow.row_number)
            .offset(skip)
            .limit(limit)
            .all()
        ],
    }


@router.get("/reviews/{review_id}/rows/{row_id}")
def row_detail(
    review_id: int,
    row_id: int,
    db: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Show all current/historical recommendations through pagination and every change."""
    get_review(db, review_id)
    row = selected_row(db, review_id, row_id)
    record = db.get(SourceRecord, row.source_record_id)
    assert record is not None
    batch = pdpj_batch(db, record.batch_id)
    recommendations = db.query(PdpjRecommendation).filter(
        PdpjRecommendation.row_id == row_id
    )
    return {
        **row_info(row),
        "original_fields": row.original_fields,
        "raw_data": record.data,
        "filename": batch.filename,
        "source_sheet": batch.source_sheet,
        "column_mapping": batch.column_mapping or {},
        "recommendations_total": recommendations.count(),
        "recommendations": [
            {
                "id": item.id,
                "fields": item.fields,
                "provenance": item.provenance,
                "validation_errors": item.validation_errors,
                "current": item.fields.get("idpel") == row.current_fields.get("idpel"),
            }
            for item in recommendations.order_by(PdpjRecommendation.id)
            .offset(skip)
            .limit(limit)
            .all()
        ],
        "history": [
            {
                "id": change.id,
                "action": change.action,
                "actor": change.actor,
                "reason": change.reason,
                "before": change.before,
                "after": change.after,
                "sources": change.sources,
                "created_at": change.created_at,
            }
            for change in db.query(PdpjChange)
            .filter(PdpjChange.row_id == row_id)
            .order_by(PdpjChange.id.desc())
            .all()
        ],
    }


@router.patch("/reviews/{review_id}/rows/{row_id}")
def edit_row(
    review_id: int, row_id: int, req: EditRow, db: DbSession
) -> dict[str, Any]:
    """Apply manual partial corrections and retain before/after history."""
    review = get_review(db, review_id, req.revision)
    row = selected_row(db, review_id, row_id)
    update_fields(db, review, row, req.fields, req.actor, req.reason)
    return {"revision": review.revision, **row_info(row)}


@router.post("/reviews/{review_id}/rows/{row_id}/apply")
def apply_recommendation(
    review_id: int, row_id: int, req: ApplyRecommendation, db: DbSession
) -> dict[str, Any]:
    """Fill selected fields from exactly one stored recommendation."""
    review = get_review(db, review_id, req.revision)
    row = selected_row(db, review_id, row_id)
    recommendation = db.get(PdpjRecommendation, req.recommendation_id)
    if recommendation is None or recommendation.row_id != row.id:
        raise HTTPException(404, "Rekomendasi pada baris ini tidak ditemukan")
    update_fields(
        db,
        review,
        row,
        {key: recommendation.fields.get(key) for key in req.fields},
        req.actor,
        req.reason,
        recommendation,
        req.overwrite,
    )
    return {"revision": review.revision, **row_info(row)}


@router.post("/reviews/{review_id}/rows/{row_id}/decision")
def decide_row(
    review_id: int, row_id: int, req: DecideRow, db: DbSession
) -> dict[str, Any]:
    """Require a reason for unresolved exceptions and preserve reopening decisions."""
    review = get_review(db, review_id, req.revision)
    row = selected_row(db, review_id, row_id)
    refresh_rows(db, review, row)
    if req.action == "reviewed" and row.issues:
        raise HTTPException(409, "Baris masih memiliki masalah yang perlu diselesaikan")
    if req.action == "exception" and not req.reason.strip():
        raise HTTPException(422, "Alasan pengecualian wajib diisi")
    before = before_change(row)
    row.reviewed = req.action != "reopen"
    row.exception = req.action == "exception"
    row.exception_reason = req.reason.strip() if row.exception else ""
    record_change(db, row, req.action, req.actor, req.reason.strip(), before)
    review.revision += 1
    db.commit()
    return {"revision": review.revision, **row_info(row)}


@router.post("/reviews/{review_id}/complete")
def finish_review(review_id: int, req: ReviewAction, db: DbSession) -> dict[str, Any]:
    """Finalize clean rows together; exceptions must already carry explicit reasons."""
    try:
        review = get_review(db, review_id, req.revision)
        complete_validation(db, review, req.actor)
        return review_info(review)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "penyelesaian PDPJ") from exc


@router.post("/reviews/{review_id}/complete-with-exceptions")
def finish_with_exceptions(
    review_id: int, req: CompleteWithExceptions, db: DbSession
) -> dict[str, Any]:
    """Finalize after an explicit, audited deferral of all remaining problem rows."""
    try:
        review = get_review(db, review_id, req.revision)
        added = complete_validation(
            db,
            review,
            req.actor,
            exception_reason=req.reason,
            expected_unresolved=req.expected_unresolved,
        )
        return {**review_info(review), "exceptions_added": added}
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        raise database_write_error(
            db, exc, "penyelesaian PDPJ dengan pengecualian"
        ) from exc
