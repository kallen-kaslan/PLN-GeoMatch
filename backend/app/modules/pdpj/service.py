"""Validate PDPJ identity against pinned master observations and retain every decision."""

from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.pdpj import PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.upload.normalization import (
    ALIASES,
    extract_standard_fields,
    validate_fields,
    with_reference_fields,
)
from app.pdpj_warning_schema import DUPLICATE_IDPEL
from app.performance import timed

MASTER_TYPES = {DatasetType.PRABAYAR, DatasetType.PASCABAYAR, DatasetType.DIL}
EDITABLE_FIELDS = set(ALIASES) - {"verif"}
VALIDATION_CHUNK_ROWS = 400


def lock_review_session(db: Session) -> None:
    """Serialize SQLite writes before loading revisions; PostgreSQL locks review rows."""
    if db.get_bind().dialect.name == "sqlite":
        connection = db.connection()
        driver = connection.connection.driver_connection
        assert driver is not None
        if not driver.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")


def pdpj_batch(db: Session, batch_id: int) -> UploadBatch:
    """Resolve exactly the requested PDPJ file."""
    batch = db.get(UploadBatch, batch_id)
    if batch is None or batch.dataset_type != DatasetType.PDPJ:
        raise HTTPException(404, "Berkas PDPJ tidak ditemukan")
    return batch


def get_review(db: Session, review_id: int, revision: int | None = None) -> PdpjReview:
    """Reject edits to completed or stale review versions."""
    if revision is not None:
        lock_review_session(db)
    review = (
        db.query(PdpjReview)
        .filter(PdpjReview.id == review_id)
        .with_for_update()
        .populate_existing()
        .first()
        if revision is not None
        else db.get(PdpjReview, review_id)
    )
    if review is None:
        raise HTTPException(404, "Pemeriksaan PDPJ tidak ditemukan")
    if revision is not None:
        if review.processing and (
            review.processing["state"] == "running"
            or not review.processing["processed_rows"]
        ):
            raise HTTPException(
                409,
                "Jeda pemeriksaan dan tunggu bagian aktif tersimpan sebelum meninjau hasil.",
            )
        if review.status != "in_progress":
            raise HTTPException(
                409,
                "Pemeriksaan sudah selesai. Buat pemeriksaan ulang untuk perubahan berikutnya.",
            )
        if review.revision != revision:
            raise HTTPException(
                409, "Data telah berubah. Muat ulang pemeriksaan sebelum menyimpan."
            )
    return review


def completed_review(
    db: Session, batch_id: int, review_id: int | None = None
) -> PdpjReview:
    """Pin an approved version, or resolve the latest publication of the current review."""
    review = (
        db.get(PdpjReview, review_id)
        if review_id is not None
        else db.query(PdpjReview)
        .filter(PdpjReview.batch_id == batch_id, PdpjReview.source_review_id.is_(None))
        .order_by(PdpjReview.id.desc())
        .first()
    )
    if review is not None and review_id is None and review.status != "completed":
        review = (
            db.query(PdpjReview)
            .filter(
                PdpjReview.source_review_id == review.id,
                PdpjReview.status == "completed",
            )
            .order_by(PdpjReview.id.desc())
            .first()
        )
    if review is None or review.batch_id != batch_id or review.status != "completed":
        raise ValueError(
            "Selesaikan validasi PDPJ terlebih dahulu melalui menu Data PDPJ"
        )
    return review


def pending_pdpj_records(db: Session, review: PdpjReview) -> Iterator[SourceRecord]:
    """Reserve the raw remainder pinned at publication, independently of later progress."""
    if review.source_review_id is not None and review.publication:
        yield from (
            db.query(SourceRecord)
            .filter(
                SourceRecord.batch_id == review.batch_id,
                SourceRecord.id > review.publication["last_source_id"],
            )
            .order_by(SourceRecord.id)
            .yield_per(400)
        )


def normalized(record: SourceRecord, batch: UploadBatch) -> dict[str, Any]:
    """Read mapped source values without modifying the uploaded cells."""
    fields = extract_standard_fields(record.data or {}, batch.column_mapping)
    fields["tglbaca"] = fields["tglbaca"] or batch.period
    return fields


def add_recommendations(db: Session, review: PdpjReview, rows: list[PdpjRow]) -> None:
    """Snapshot all matching observations, even those with incomplete/invalid coordinates."""
    by_idpel: dict[str, list[PdpjRow]] = {}
    for row in rows:
        idpel = row.current_fields.get("idpel")
        if idpel and idpel.isascii() and idpel.isdigit():
            by_idpel.setdefault(idpel, []).append(row)
    known = {
        (item.row_id, item.source_record_id)
        for item in db.query(PdpjRecommendation)
        .join(PdpjRow, PdpjRow.id == PdpjRecommendation.row_id)
        .filter(
            PdpjRow.review_id == review.id, PdpjRow.id.in_([row.id for row in rows])
        )
        .all()
    }
    identifiers = list(by_idpel)
    pending = []
    for offset in range(0, len(identifiers), 400):
        observations = (
            db.query(SourceRecord, UploadBatch)
            .join(UploadBatch, SourceRecord.batch_id == UploadBatch.id)
            .filter(
                UploadBatch.id.in_(review.master_batch_ids),
                UploadBatch.status == BatchStatus.COMPLETED,
                UploadBatch.dataset_type.in_(MASTER_TYPES),
                SourceRecord.idpel.in_(identifiers[offset : offset + 400]),
            )
            .order_by(UploadBatch.id, SourceRecord.id)
            .all()
        )
        for record, batch in observations:
            fields = normalized(record, batch)
            errors = fields.pop("validation_errors")
            for row in by_idpel.get(fields["idpel"], []):
                if (row.id, record.id) not in known:
                    pending.append(
                        {
                            "row_id": row.id,
                            "source_record_id": record.id,
                            "fields": fields,
                            "validation_errors": errors,
                            "provenance": {
                                "batch_id": batch.id,
                                "filename": batch.filename,
                                "dataset_type": batch.dataset_type.value,
                                "row_number": record.row_number,
                                "source_sheet": batch.source_sheet,
                                "period": fields["tglbaca"],
                            },
                        }
                    )
                    if len(pending) >= 400:
                        db.bulk_insert_mappings(PdpjRecommendation.__mapper__, pending)
                        pending.clear()
    if pending:
        db.bulk_insert_mappings(PdpjRecommendation.__mapper__, pending)
    db.flush()


def refresh_rows(
    db: Session,
    review: PdpjReview,
    focus: PdpjRow | None = None,
    previous_idpel: str | None = None,
) -> list[PdpjRow]:
    """Keep existence, coordinate completeness, duplicates, and review status separate."""
    query = db.query(PdpjRow).filter(PdpjRow.review_id == review.id)
    if focus is not None:
        identities = {
            value
            for value in (focus.current_fields.get("idpel"), previous_idpel)
            if value
        }
        query = query.filter(
            or_(
                PdpjRow.id == focus.id,
                PdpjRow.current_fields["idpel"].as_string().in_(identities),
            )
        )
    rows = query.order_by(PdpjRow.row_number).all()
    counts = Counter(
        row.current_fields.get("idpel")
        for row in rows
        if row.current_fields.get("idpel")
    )
    recommendations: Counter = Counter()
    identity = PdpjRecommendation.fields["idpel"].as_string()
    recommendations_query = (
        db.query(PdpjRecommendation.row_id, identity, func.count(PdpjRecommendation.id))
        .join(PdpjRow, PdpjRow.id == PdpjRecommendation.row_id)
        .filter(PdpjRow.review_id == review.id)
    )
    if focus is not None:
        recommendations_query = recommendations_query.filter(
            or_(
                PdpjRow.id == focus.id,
                PdpjRow.current_fields["idpel"].as_string().in_(identities),
            )
        )
    for row_id, idpel, count in recommendations_query.group_by(
        PdpjRecommendation.row_id, identity
    ).all():
        recommendations[(row_id, idpel)] = count
    for row in rows:
        refresh_row(row, counts, recommendations)
    db.flush()
    return rows


def refresh_row(row: PdpjRow, counts: Counter, recommendations: Counter) -> None:
    """Use the same validation rules for individual edits and chunked completion."""
    fields = extract_standard_fields(row.current_fields)
    fields["validation_errors"] = list(
        {
            (error["field"], error["code"]): error
            for error in [
                *fields["validation_errors"],
                *row.current_fields.get("validation_errors", []),
            ]
        }.values()
    )
    issues = [
        item
        for item in validate_fields(fields, DatasetType.PDPJ)
        if item["code"] != DUPLICATE_IDPEL
    ]
    idpel = fields["idpel"]
    row.recommendation_count = recommendations[(row.id, idpel)]
    row.existence = (
        "empty"
        if not idpel
        else "invalid"
        if any(item["field"] == "idpel" for item in issues)
        else "found"
        if row.recommendation_count
        else "not_found"
    )
    if row.existence == "not_found":
        issues.append({"field": "idpel", "code": "idpel_tidak_ditemukan"})
    row.warnings = [
        item for item in (row.warnings or []) if item.get("code") != DUPLICATE_IDPEL
    ]
    if idpel and counts[idpel] > 1:
        row.warnings = [*row.warnings, {"field": "idpel", "code": DUPLICATE_IDPEL}]
    for field in ("lat", "lon"):
        if fields[field] is None and not any(item["field"] == field for item in issues):
            issues.append({"field": field, "code": "koordinat_wajib_diisi"})
    if row.issues != issues and not row.exception:
        row.reviewed = False
    row.issues = issues


def validation_chunks(db: Session, review: PdpjReview) -> Iterator[list[PdpjRow]]:
    """Recheck a large review without loading every row and recommendation into RAM."""
    identity = PdpjRow.current_fields["idpel"].as_string()
    counts = Counter(
        dict(
            db.query(identity, func.count(PdpjRow.id))
            .filter(
                PdpjRow.review_id == review.id, identity.isnot(None), identity != ""
            )
            .group_by(identity)
            .having(func.count(PdpjRow.id) > 1)
            .all()
        )
    )
    last_id = 0
    while True:
        rows = (
            db.query(PdpjRow)
            .filter(PdpjRow.review_id == review.id, PdpjRow.id > last_id)
            .order_by(PdpjRow.id)
            .limit(VALIDATION_CHUNK_ROWS)
            .all()
        )
        if not rows:
            return
        recommendation_identity = PdpjRecommendation.fields["idpel"].as_string()
        recommendations = Counter(
            {
                (row_id, idpel): count
                for row_id, idpel, count in db.query(
                    PdpjRecommendation.row_id,
                    recommendation_identity,
                    func.count(PdpjRecommendation.id),
                )
                .filter(PdpjRecommendation.row_id.in_([row.id for row in rows]))
                .group_by(PdpjRecommendation.row_id, recommendation_identity)
                .all()
            }
        )
        for row in rows:
            refresh_row(row, counts, recommendations)
        last_id = rows[-1].id
        yield rows
        db.flush()
        for row in rows:
            db.expunge(row)


@timed("pdpj.create_review")
def create_review(
    db: Session,
    batch_id: int,
    master_batch_ids: list[int] | None,
    *,
    incremental: bool = False,
) -> PdpjReview:
    """Pin sources and persist a checkpoint before processing any source rows."""
    lock_review_session(db)
    batch = (
        db.query(UploadBatch)
        .filter(UploadBatch.id == batch_id)
        .with_for_update()
        .first()
    )
    if batch is None or batch.dataset_type != DatasetType.PDPJ:
        raise HTTPException(404, "Berkas PDPJ tidak ditemukan")
    if batch.status != BatchStatus.COMPLETED:
        raise HTTPException(409, "Konfirmasi mapping PDPJ terlebih dahulu")
    masters = db.query(UploadBatch).filter(
        UploadBatch.dataset_type.in_(MASTER_TYPES),
        UploadBatch.status == BatchStatus.COMPLETED,
    )
    ids = (
        sorted(set(master_batch_ids))
        if master_batch_ids is not None
        else sorted(item.id for item in masters.all())
    )
    if not ids or masters.filter(UploadBatch.id.in_(ids)).count() != len(ids):
        raise HTTPException(
            422, "Pilih minimal satu berkas master yang sudah dikonfirmasi"
        )
    # Mapping confirmation locks the same upload rows; source interpretation cannot
    # change while the recommendation snapshot is being materialized.
    masters.filter(UploadBatch.id.in_(ids)).order_by(
        UploadBatch.id
    ).with_for_update().all()
    previous = (
        db.query(PdpjReview)
        .filter(PdpjReview.batch_id == batch_id, PdpjReview.source_review_id.is_(None))
        .order_by(PdpjReview.id.desc())
        .first()
    )
    if previous and previous.status == "in_progress":
        if previous.master_batch_ids != ids:
            raise HTTPException(
                409,
                "Selesaikan pemeriksaan yang sedang berjalan sebelum mengganti sumber master",
            )
        return previous
    total = db.query(SourceRecord).filter(SourceRecord.batch_id == batch_id).count()
    if not total:
        raise HTTPException(422, "Berkas PDPJ tidak memiliki baris data")
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    review = PdpjReview(
        batch_id=batch_id,
        master_batch_ids=ids,
        processing={
            "state": "running",
            "stage": "matching",
            "total_rows": total,
            "processed_rows": 0,
            "validated_rows": 0,
            "last_source_id": 0,
            "last_row_number": None,
            "last_validated_id": 0,
            "previous_review_id": previous.id if previous else None,
            "started_at": now,
            "updated_at": now,
            "elapsed_seconds": 0.0,
            "error": None,
        },
    )
    db.add(review)
    db.commit()
    # Preserve the synchronous contract for existing integrations. The UI uses
    # incremental mode and requests exactly one durable chunk at a time.
    if not incremental:
        while review.processing and review.processing["state"] == "running":
            review = advance_review(db, review.id, review.revision)
    return review


def processing_review(db: Session, review_id: int) -> PdpjReview:
    """Serialize checkpoints, stop requests, and competing browser sessions."""
    lock_review_session(db)
    review = (
        db.query(PdpjReview)
        .filter(PdpjReview.id == review_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if review is None:
        raise HTTPException(404, "Pemeriksaan PDPJ tidak ditemukan")
    return review


def control_processing(db: Session, review_id: int, state: str) -> PdpjReview:
    """Pause after the active transaction, or resume the exact saved snapshot."""
    review = processing_review(db, review_id)
    if (
        review.status == "completed"
        or not review.processing
        or review.processing["state"] == "ready"
    ):
        return review
    review.processing = {
        **review.processing,
        "state": state,
        "error": None,
        "updated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
    }
    review.revision += 1
    db.commit()
    return review


def validate_processing_rows(
    db: Session, review: PdpjReview, rows: list[PdpjRow]
) -> None:
    """Validate one chunk, including duplicate identities across chunk boundaries."""
    identity = PdpjRow.current_fields["idpel"].as_string()
    identities = {row.current_fields.get("idpel") for row in rows} - {None, ""}
    counts = Counter(
        dict(
            db.query(identity, func.count(PdpjRow.id))
            .filter(PdpjRow.review_id == review.id, identity.in_(identities))
            .group_by(identity)
            .all()
        )
    )
    recommendation_identity = PdpjRecommendation.fields["idpel"].as_string()
    recommendations = Counter(
        {
            (row_id, idpel): count
            for row_id, idpel, count in db.query(
                PdpjRecommendation.row_id,
                recommendation_identity,
                func.count(PdpjRecommendation.id),
            )
            .filter(PdpjRecommendation.row_id.in_([row.id for row in rows]))
            .group_by(PdpjRecommendation.row_id, recommendation_identity)
            .all()
        }
    )
    for row in rows:
        refresh_row(row, counts, recommendations)


def match_processing_chunk(
    db: Session, review: PdpjReview, progress: dict[str, Any], chunk_size: int = 400
) -> None:
    """Persist full matching results together with their source cursor."""
    batch = pdpj_batch(db, review.batch_id)
    previous_id = progress["previous_review_id"]
    records = (
        db.query(SourceRecord)
        .filter(
            SourceRecord.batch_id == batch.id,
            SourceRecord.id > progress["last_source_id"],
        )
        .order_by(SourceRecord.id)
        .limit(min(VALIDATION_CHUNK_ROWS, chunk_size))
        .all()
    )
    if not records and progress["processed_rows"] != progress["total_rows"]:
        raise ValueError("Jumlah baris sumber tidak sesuai checkpoint")
    if records:
        source_ids = [record.id for record in records]
        previous_rows = (
            {
                row.source_record_id: row
                for row in db.query(PdpjRow)
                .filter(
                    PdpjRow.review_id == previous_id,
                    PdpjRow.source_record_id.in_(source_ids),
                )
                .all()
            }
            if previous_id
            else {}
        )
        pending: list[dict[str, Any]] = []
        for record in records:
            fields = normalized(record, batch)
            prior = previous_rows.get(record.id)
            pending.append(
                {
                    "review_id": review.id,
                    "source_record_id": record.id,
                    "row_number": record.row_number
                    or progress["processed_rows"] + len(pending) + 2,
                    "original_fields": fields,
                    "current_fields": with_reference_fields(
                        prior.current_fields, record.data or {}, batch.column_mapping
                    )
                    if prior
                    else fields,
                    "existence": "empty",
                }
            )
        db.bulk_insert_mappings(PdpjRow.__mapper__, pending)
        rows = (
            db.query(PdpjRow)
            .filter(
                PdpjRow.review_id == review.id, PdpjRow.source_record_id.in_(source_ids)
            )
            .order_by(PdpjRow.id)
            .all()
        )
        for row in rows:
            prior = previous_rows.get(row.source_record_id)
            if prior:
                record_change(
                    db,
                    row,
                    "carried_forward",
                    "Sistem",
                    "Nilai dari pemeriksaan sebelumnya dipertahankan untuk diperiksa ulang",
                    {
                        "fields": row.original_fields,
                        "reviewed": False,
                        "exception": False,
                        "exception_reason": "",
                    },
                    {
                        "previous_review_id": prior.review_id,
                        "previous_row_id": prior.id,
                    },
                )
        add_recommendations(db, review, rows)
        validate_processing_rows(db, review, rows)
        db.flush()
        progress["last_source_id"] = records[-1].id
        progress["last_row_number"] = rows[-1].row_number
        progress["processed_rows"] += len(rows)
    if progress["processed_rows"] == progress["total_rows"]:
        progress["stage"] = "validating"


def advance_review(
    db: Session, review_id: int, revision: int, chunk_size: int = 400
) -> PdpjReview:
    """Commit results and their cursor atomically; a failed chunk is retried whole."""
    review = processing_review(db, review_id)
    if review.revision != revision:
        raise HTTPException(
            409, "Progres telah berubah. Muat ulang sebelum melanjutkan."
        )
    if not review.processing or review.processing["state"] == "ready":
        return review
    if review.processing["state"] != "running":
        raise HTTPException(409, "Proses dijeda. Pilih Lanjutkan pemeriksaan.")
    progress = dict(review.processing)
    started = monotonic()
    try:
        if progress["stage"] == "matching":
            match_processing_chunk(db, review, progress, chunk_size)
        else:
            rows = (
                db.query(PdpjRow)
                .filter(
                    PdpjRow.review_id == review.id,
                    PdpjRow.id > progress["last_validated_id"],
                )
                .order_by(PdpjRow.id)
                .limit(min(VALIDATION_CHUNK_ROWS, chunk_size))
                .all()
            )
            validate_processing_rows(db, review, rows)
            if not rows and progress["validated_rows"] != progress["total_rows"]:
                raise ValueError("Jumlah hasil tidak sesuai checkpoint validasi")
            if rows:
                progress["last_validated_id"] = rows[-1].id
                progress["validated_rows"] += len(rows)
            if progress["validated_rows"] == progress["total_rows"]:
                progress.update(state="ready", stage="done")
        progress["elapsed_seconds"] += monotonic() - started
        progress["updated_at"] = datetime.now(UTC).replace(tzinfo=None).isoformat()
        review.processing = progress
        review.revision += 1
        db.commit()
        return review
    except Exception as exc:
        db.rollback()
        # Keep the earlier committed cursor, never the failed in-memory cursor.
        try:
            saved = processing_review(db, review_id)
            saved.processing = {
                **(saved.processing or {}),
                "state": "failed",
                "error": "Bagian terakhir belum tersimpan. Lanjutkan untuk mencoba kembali.",
                "updated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
            }
            saved.revision += 1
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        if isinstance(exc, SQLAlchemyError):
            raise
        raise HTTPException(
            500,
            "Pemeriksaan terhenti. Hasil sebelumnya tetap tersimpan; muat ulang dan lanjutkan.",
        ) from exc


def record_change(
    db: Session,
    row: PdpjRow,
    action: str,
    actor: str,
    reason: str,
    before: dict[str, Any],
    sources: dict[str, Any] | None = None,
) -> None:
    """Append a complete before/after snapshot and the selected field provenance."""
    db.add(
        PdpjChange(
            row_id=row.id,
            action=action,
            actor=actor,
            reason=reason,
            before=before,
            after={
                "fields": row.current_fields,
                "reviewed": row.reviewed,
                "exception": row.exception,
                "exception_reason": row.exception_reason,
            },
            sources=sources or {},
        )
    )


def before_change(row: PdpjRow) -> dict[str, Any]:
    """Capture row state before a decision or correction."""
    return {
        "fields": dict(row.current_fields),
        "reviewed": row.reviewed,
        "exception": row.exception,
        "exception_reason": row.exception_reason,
    }


def update_fields(
    db: Session,
    review: PdpjReview,
    row: PdpjRow,
    changes: dict[str, Any],
    actor: str,
    reason: str,
    recommendation: PdpjRecommendation | None = None,
    overwrite: bool = False,
) -> None:
    """Validate partial edits and require explicit consent before replacing filled values."""
    if not changes or set(changes) - EDITABLE_FIELDS:
        raise HTTPException(422, "Pilih field pelengkapan yang dikenali")
    if recommendation and recommendation.fields.get("idpel") != row.current_fields.get(
        "idpel"
    ):
        raise HTTPException(409, "Rekomendasi tidak sesuai IDPEL saat ini")
    occupied = any(
        row.current_fields.get(key) not in (None, "", "-")
        and row.current_fields.get(key) != value
        for key, value in changes.items()
    )
    if occupied and (not reason.strip() or (recommendation and not overwrite)):
        raise HTTPException(
            409, "Penggantian nilai terisi memerlukan alasan dan persetujuan penimpaan"
        )
    if recommendation:
        bad_fields = {item["field"] for item in recommendation.validation_errors}
        if any(
            value in (None, "", "-") or key in bad_fields
            for key, value in changes.items()
        ):
            raise HTTPException(
                422, "Field rekomendasi kosong atau tidak valid tidak dapat diterapkan"
            )
    source = db.get(SourceRecord, row.source_record_id)
    batch = db.get(UploadBatch, review.batch_id)
    assert source is not None and batch is not None
    baseline = with_reference_fields(
        row.current_fields, source.data or {}, batch.column_mapping
    )
    merged = {**baseline, **changes}
    fields = extract_standard_fields(merged)
    if any(error["field"] in changes for error in fields["validation_errors"]):
        raise HTTPException(
            422, "Periksa format IDPEL, koordinat, atau daya yang diisi"
        )
    fields["validation_errors"] = list(
        {
            (error["field"], error["code"]): error
            for error in [
                *fields["validation_errors"],
                *(
                    error
                    for error in row.current_fields.get("validation_errors", [])
                    if error["field"] not in changes
                ),
            ]
        }.values()
    )
    before = before_change(row)
    row.current_fields = fields
    row.reviewed = row.exception = False
    row.exception_reason = ""
    db.flush()
    add_recommendations(db, review, [row])
    refresh_rows(db, review, row, before["fields"].get("idpel"))
    sources = (
        {
            key: {"recommendation_id": recommendation.id, **recommendation.provenance}
            for key in changes
        }
        if recommendation
        else {key: {"manual": True} for key in changes}
    )
    record_change(
        db,
        row,
        "recommendation" if recommendation else "manual",
        actor,
        reason,
        before,
        sources,
    )
    review.revision += 1
    db.commit()


def complete_validation(
    db: Session,
    review: PdpjReview,
    actor: str,
    *,
    exception_reason: str | None = None,
    expected_unresolved: int | None = None,
) -> tuple[int, PdpjReview]:
    """Approve a fixed version while keeping a partial review's cursor resumable."""
    latest = (
        db.query(PdpjReview)
        .filter(PdpjReview.source_review_id == review.id)
        .order_by(PdpjReview.id.desc())
        .first()
    )
    if (
        latest
        and latest.publication
        and latest.publication["source_revision"] + 1 == review.revision
    ):
        return 0, latest
    total = added = 0
    for rows in validation_chunks(db, review):
        changes = []
        for row in rows:
            total += 1
            unresolved = bool(row.issues) and not row.exception
            if unresolved and exception_reason is None:
                raise HTTPException(
                    409,
                    "Masih ada masalah PDPJ. Lengkapi data atau simpan alasan pengecualian per baris.",
                )
            if unresolved or not row.reviewed:
                before = before_change(row)
                row.reviewed = True
                if unresolved:
                    row.exception = True
                    row.exception_reason = exception_reason or ""
                    added += 1
                changes.append(
                    {
                        "row_id": row.id,
                        "action": "exception" if unresolved else "finalized",
                        "actor": actor,
                        "reason": exception_reason
                        if unresolved
                        else "Persetujuan saat penyelesaian validasi",
                        "before": before,
                        "after": before_change(row),
                        "sources": {
                            "bulk": True,
                            "review_id": review.id,
                            "affected_rows": expected_unresolved,
                        }
                        if unresolved
                        else {},
                    }
                )
        if changes:
            db.bulk_insert_mappings(PdpjChange.__mapper__, changes)
    if not total:
        raise HTTPException(409, "Pemeriksaan PDPJ tidak memiliki baris data")
    if expected_unresolved is not None and added != expected_unresolved:
        raise HTTPException(
            409,
            "Jumlah masalah berubah. Muat ulang pemeriksaan dan tinjau kembali sebelum melanjutkan.",
        )
    db.flush()
    if review.processing and review.processing["state"] != "ready":
        from app.modules.pdpj.publications import publish_saved_rows

        published = publish_saved_rows(db, review, actor, total)
    else:
        review.status = "completed"
        review.completed_at = datetime.now(UTC).replace(tzinfo=None)
        review.completed_by = actor
        versions = (
            db.query(PdpjReview)
            .filter(PdpjReview.source_review_id == review.id)
            .count()
        )
        if versions:
            review.publication = {
                "version": versions + 1,
                "row_count": total,
                "total_rows": total,
                "is_partial": False,
            }
        published = review
    review.revision += 1
    db.commit()
    return added, published
