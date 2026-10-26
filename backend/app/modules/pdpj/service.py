"""Validate PDPJ identity against pinned master observations and retain every decision."""

from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.pdpj import PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.upload.normalization import (
    ALIASES,
    extract_standard_fields,
    validate_fields,
    with_reference_fields,
)

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
    """Pin one completed validation; never fall back from an unfinished latest review."""
    review = (
        db.get(PdpjReview, review_id)
        if review_id is not None
        else db.query(PdpjReview)
        .filter(PdpjReview.batch_id == batch_id)
        .order_by(PdpjReview.id.desc())
        .first()
    )
    if review is None or review.batch_id != batch_id or review.status != "completed":
        raise ValueError(
            "Selesaikan validasi PDPJ terlebih dahulu melalui menu Data PDPJ"
        )
    return review


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
        .filter(PdpjRow.review_id == review.id)
        .all()
    }
    identifiers = list(by_idpel)
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
                    db.add(
                        PdpjRecommendation(
                            row_id=row.id,
                            source_record_id=record.id,
                            fields=fields,
                            validation_errors=errors,
                            provenance={
                                "batch_id": batch.id,
                                "filename": batch.filename,
                                "dataset_type": batch.dataset_type.value,
                                "row_number": record.row_number,
                                "source_sheet": batch.source_sheet,
                                "period": fields["tglbaca"],
                            },
                        )
                    )
    db.flush()


def refresh_rows(db: Session, review: PdpjReview) -> list[PdpjRow]:
    """Keep existence, coordinate completeness, duplicates, and review status separate."""
    rows = (
        db.query(PdpjRow)
        .filter(PdpjRow.review_id == review.id)
        .order_by(PdpjRow.row_number)
        .all()
    )
    counts = Counter(
        row.current_fields.get("idpel")
        for row in rows
        if row.current_fields.get("idpel")
    )
    recommendations: Counter = Counter()
    for item in (
        db.query(PdpjRecommendation)
        .join(PdpjRow, PdpjRow.id == PdpjRecommendation.row_id)
        .filter(PdpjRow.review_id == review.id)
        .all()
    ):
        recommendations[(item.row_id, item.fields.get("idpel"))] += 1
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
    issues = validate_fields(fields, DatasetType.PDPJ)
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
    if idpel and counts[idpel] > 1:
        issues.append({"field": "idpel", "code": "idpel_berulang_pdpj"})
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


def create_review(
    db: Session, batch_id: int, master_batch_ids: list[int] | None
) -> PdpjReview:
    """Create a validation snapshot and leave every source row untouched."""
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
        .filter(PdpjReview.batch_id == batch_id)
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
    previous_rows = (
        {
            row.source_record_id: row
            for row in db.query(PdpjRow).filter(PdpjRow.review_id == previous.id).all()
        }
        if previous
        else {}
    )
    records = (
        db.query(SourceRecord)
        .filter(SourceRecord.batch_id == batch_id)
        .order_by(SourceRecord.id)
        .all()
    )
    if not records:
        raise HTTPException(422, "Berkas PDPJ tidak memiliki baris data")
    review = PdpjReview(batch_id=batch_id, master_batch_ids=ids)
    db.add(review)
    db.flush()
    rows = []
    for number, record in enumerate(records, 2):
        fields = normalized(record, batch)
        # Validation issues are recomputed from the canonical values; original bad
        # cells remain accessible in raw_data and original_fields.validation_errors.
        prior = previous_rows.get(record.id)
        row = PdpjRow(
            review_id=review.id,
            source_record_id=record.id,
            row_number=record.row_number or number,
            original_fields=fields,
            current_fields=with_reference_fields(
                prior.current_fields, record.data or {}, batch.column_mapping
            )
            if prior
            else fields,
            existence="empty",
        )
        db.add(row)
        rows.append(row)
    db.flush()
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
                {"previous_review_id": prior.review_id, "previous_row_id": prior.id},
            )
    add_recommendations(db, review, rows)
    refresh_rows(db, review)
    db.commit()
    return review


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
    refresh_rows(db, review)
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
) -> int:
    """Finalize only clean rows or explicit exceptions; completion is immutable."""
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
            db.bulk_insert_mappings(PdpjChange, changes)
    if not total:
        raise HTTPException(409, "Pemeriksaan PDPJ tidak memiliki baris data")
    if expected_unresolved is not None and added != expected_unresolved:
        raise HTTPException(
            409,
            "Jumlah masalah berubah. Muat ulang pemeriksaan dan tinjau kembali sebelum melanjutkan.",
        )
    review.status = "completed"
    review.completed_at = datetime.now(UTC).replace(tzinfo=None)
    review.completed_by = actor
    review.revision += 1
    db.commit()
    return added
