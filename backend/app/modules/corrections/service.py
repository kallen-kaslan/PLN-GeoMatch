"""Scope categorized checks to one completed PDPJ review and immutable source batches."""

import enum
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.correction import CorrectionAttempt, CorrectionCheck
from app.models.matching import MatchingRun, ProcessStatus, ReconciliationProcess
from app.models.pdpj import PdpjReview
from app.models.upload import BatchStatus, DatasetType, UploadBatch
from app.modules.pdpj.service import completed_review, lock_review_session
from app.modules.spatial.pipeline import pin_pipeline_sources
from app.modules.upload.normalization import (
    canonical_mapping,
    clean_text,
    normalize_column_name,
)


class CorrectionKind(str, enum.Enum):
    NOT_FOUND = "idpel_tidak_ketemu"
    EMPTY = "idpel_kosong"


CORRECTION_TYPES = {DatasetType.IDPEL_TIDAK_KETEMU, DatasetType.IDPEL_KOSONG}
# Agenda values remain in the source/evidence, but do not identify duplicate targets.
REFERENCE_FIELDS = {
    "meter": ("meter_ref", "nomor_meter_kwh", "nomor_meter_prepaid"),
    "survey": ("survey_ref",),
}


def reference_value(value: Any) -> str | None:
    """Keep leading zeroes in real identifiers; blank/all-zero values prove no collision."""
    text = clean_text(value)
    return text.upper() if text and text.strip("0") else None


def reference_tokens(
    fields: dict[str, Any], raw: dict[str, Any], mapping: dict[str, str] | None
) -> dict[str, set[str]]:
    """Only shared meters/survey references block correction; agendas are descriptive."""
    result = {
        kind: {value for key in keys if (value := reference_value(fields.get(key)))}
        for kind, keys in REFERENCE_FIELDS.items()
    }
    if all(REFERENCE_FIELDS[kind][0] in fields for kind in REFERENCE_FIELDS):
        return result
    selected = canonical_mapping(mapping).get("target_ref")
    if not selected:
        names = {normalize_column_name(key): key for key in raw}
        selected = next(
            (
                names[key]
                for key in ("nomormeter", "notmeter", "idtitik", "noagenda", "ref")
                if key in names
            ),
            None,
        )
    column = normalize_column_name(selected or "")
    kind = (
        "meter"
        if column in {"nomormeter", "notmeter", "nomormeterkwh", "nomormeterprepaid"}
        else "survey"
        if column in {"idtitik", "ref", "referensisurvei"}
        else None
    )
    primary = {"meter": "meter_ref", "survey": "survey_ref"}
    if (
        kind
        and primary[kind] not in fields
        and (value := reference_value(fields.get("target_ref")))
    ):
        result[kind].add(value.upper())
    return result


def source_batch(db: Session, kind: CorrectionKind, batch_id: int) -> UploadBatch:
    """Keep category ownership explicit, including empty result sets."""
    batch = db.get(UploadBatch, batch_id)
    if batch is None or batch.dataset_type != DatasetType(kind.value):
        raise HTTPException(404, "Berkas pada kategori koreksi ini tidak ditemukan")
    return batch


def check_process(
    db: Session, kind: CorrectionKind, process_id: int
) -> tuple[CorrectionCheck, ReconciliationProcess]:
    """Reject other categories, legacy processes, and missing checks."""
    check = db.get(CorrectionCheck, process_id)
    process = db.get(ReconciliationProcess, process_id)
    if check is None or process is None or check.category != kind.value:
        raise HTTPException(404, "Pemeriksaan pada kategori ini tidak ditemukan")
    return check, process


def selected_run(
    db: Session, process: ReconciliationProcess, generation: int | None
) -> MatchingRun | None:
    """Only publish completed attempts; queued searches cannot masquerade as results."""
    number = generation if generation is not None else process.current_generation
    if not number:
        return None
    run = (
        db.query(MatchingRun)
        .filter(MatchingRun.process_id == process.id, MatchingRun.generation == number)
        .first()
    )
    if run is None:
        raise HTTPException(404, "Versi pemeriksaan tidak ditemukan")
    if run.status != ProcessStatus.COMPLETED:
        raise HTTPException(409, "Hasil versi pemeriksaan ini belum selesai")
    return run


def reserve_run(
    db: Session,
    process: ReconciliationProcess,
    request_key: str,
    actor: str,
    radius: float,
) -> MatchingRun:
    """Reserve all candidates in radius; never delete an earlier search or decision."""
    pending = (
        db.query(MatchingRun)
        .filter(
            MatchingRun.process_id == process.id,
            MatchingRun.status.in_([ProcessStatus.QUEUED, ProcessStatus.RUNNING]),
        )
        .first()
    )
    if pending:
        raise HTTPException(409, "Masih ada pemeriksaan yang sedang berjalan")
    latest = (
        db.query(func.max(MatchingRun.generation))
        .filter(MatchingRun.process_id == process.id)
        .scalar()
        or 0
    )
    run = MatchingRun(
        process_id=process.id,
        generation=latest + 1,
        status=ProcessStatus.QUEUED,
        radius_meters=radius,
        max_candidates=None,
    )
    db.add(run)
    process.matching_status = ProcessStatus.QUEUED
    db.flush()
    db.add(
        CorrectionAttempt(
            run_id=run.id, process_id=process.id, request_key=request_key, actor=actor
        )
    )
    db.flush()
    return run


def create_check(
    db: Session,
    kind: CorrectionKind,
    batch_id: int,
    review_id: int,
    radius: float,
    request_key: str,
    actor: str,
) -> tuple[ReconciliationProcess, MatchingRun, bool]:
    """Persist the requested operation before dispatch, with idempotent submission."""
    lock_review_session(db)
    batch = source_batch(db, kind, batch_id)
    if batch.status != BatchStatus.COMPLETED:
        raise HTTPException(409, "Selesaikan mapping berkas koreksi terlebih dahulu")
    existing = (
        db.query(CorrectionAttempt)
        .filter(CorrectionAttempt.request_key == request_key)
        .first()
    )
    if existing:
        check, process = check_process(db, kind, existing.process_id)
        run = db.get(MatchingRun, existing.run_id)
        assert run is not None
        if (
            process.target_batch_id != batch_id
            or check.pdpj_review_id != review_id
            or run.radius_meters != radius
        ):
            raise HTTPException(
                409, "Kunci permintaan sudah dipakai untuk pemeriksaan berbeda"
            )
        return process, run, False
    review = db.get(PdpjReview, review_id)
    try:
        if review is None:
            raise ValueError("Pemeriksaan PDPJ tidak ditemukan")
        completed_review(db, review.batch_id, review_id)
        sources = pin_pipeline_sources(
            db,
            None,
            None,
            review.batch_id,
            batch_id,
            pdpj_review_id=review_id,
            correction_category=kind.value,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    process = ReconciliationProcess(
        process_name=f"Koreksi {kind.value.replace('_', ' ').upper()}",
        target_batch_id=batch_id,
        radius_meters=radius,
        source_batches=sources,
    )
    db.add(process)
    db.flush()
    db.add(
        CorrectionCheck(
            process_id=process.id, category=kind.value, pdpj_review_id=review_id
        )
    )
    db.flush()
    run = reserve_run(db, process, request_key, actor, radius)
    db.commit()
    return process, run, True


def retry_check(
    db: Session,
    kind: CorrectionKind,
    process_id: int,
    latest_run_id: int,
    radius: float,
    request_key: str,
    actor: str,
) -> tuple[ReconciliationProcess, MatchingRun, bool]:
    """Use an optimistic attempt ID and serialize competing retry requests."""
    lock_review_session(db)
    _, process = check_process(db, kind, process_id)
    process = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.id == process_id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    existing = (
        db.query(CorrectionAttempt)
        .filter(CorrectionAttempt.request_key == request_key)
        .first()
    )
    if existing:
        run = db.get(MatchingRun, existing.run_id)
        assert run is not None
        if existing.process_id != process_id or run.radius_meters != radius:
            raise HTTPException(
                409, "Kunci permintaan sudah dipakai untuk pemeriksaan berbeda"
            )
        return process, run, False
    latest = (
        db.query(MatchingRun)
        .filter(MatchingRun.process_id == process_id)
        .order_by(MatchingRun.generation.desc())
        .first()
    )
    if latest is None or latest.id != latest_run_id:
        raise HTTPException(
            409, "Pemeriksaan telah berubah. Muat ulang sebelum memeriksa ulang."
        )
    run = reserve_run(db, process, request_key, actor, radius)
    db.commit()
    return process, run, True
