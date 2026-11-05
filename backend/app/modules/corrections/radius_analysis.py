"""Prepare once, checkpoint nearest distances, and reuse them for radius coverage."""

import math
from time import monotonic
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.correction import utc_now
from app.models.master_sisa import CorrectionMasterObservation, MasterSisaRecord
from app.models.matching import ProcessStatus, ReconciliationProcess
from app.models.pdpj import PdpjReview
from app.models.radius_analysis import RadiusAnalysis, RadiusAnalysisRow
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.corrections.empty_rules import COORDINATE_IDPEL_POLICY, TARGET_POLICY_KEY, target_errors
from app.modules.corrections.pdpj_index import chunk_context
from app.modules.corrections.coordinate_query import observation_window
from app.modules.corrections.observations import advance_observations
from app.modules.pdpj.service import completed_review, lock_review_session
from app.modules.spatial.engine import calculate_haversine_distance
from app.modules.spatial.master_preparation import advance_preparation
from app.modules.spatial.pipeline import pin_pipeline_sources
from app.modules.upload.normalization import extract_standard_fields, validate_fields

MAX_RADIUS = 100000.0
EARTH_RADIUS = 6371000.0


def automatic_review(db: Session) -> PdpjReview:
    """Use the most recently approved version of a file's current review."""
    current_roots = db.query(func.max(PdpjReview.id)).filter(
        PdpjReview.source_review_id.is_(None)
    ).group_by(PdpjReview.batch_id)
    review = db.query(PdpjReview).join(
        UploadBatch, UploadBatch.id == PdpjReview.batch_id
    ).filter(
        PdpjReview.status == "completed",
        UploadBatch.status == BatchStatus.COMPLETED,
        UploadBatch.dataset_type == DatasetType.PDPJ,
        func.coalesce(PdpjReview.source_review_id, PdpjReview.id).in_(current_roots),
    ).order_by(PdpjReview.completed_at.desc(), PdpjReview.id.desc()).first()
    if review is None:
        raise HTTPException(409, "Belum ada PDPJ selesai divalidasi. Selesaikan validasi di Data PDPJ, lalu lanjutkan analisis ini")
    return review


def get_analysis(db: Session, analysis_id: int, locked: bool = False) -> RadiusAnalysis:
    if locked:
        lock_review_session(db)
    query = db.query(RadiusAnalysis).filter_by(id=analysis_id)
    item = query.with_for_update().populate_existing().first() if locked else query.first()
    if item is None:
        raise HTTPException(404, "Analisis radius tidak ditemukan")
    return item


def create_analysis(db: Session, batch_id: int, review_id: int, actor: str, request_key: str) -> RadiusAnalysis:
    lock_review_session(db)
    previous = db.query(RadiusAnalysis).filter_by(request_key=request_key).first()
    if previous is not None:
        if previous.batch_id != batch_id or previous.pdpj_review_id != review_id:
            raise HTTPException(409, "Permintaan sudah digunakan untuk analisis berbeda")
        return previous
    batch = db.get(UploadBatch, batch_id)
    review = db.get(PdpjReview, review_id)
    if batch is None or batch.dataset_type not in {DatasetType.IDPEL_KOSONG, DatasetType.IDPEL_TIDAK_KETEMU}:
        raise HTTPException(404, "Unggahan koreksi tidak ditemukan")
    if batch.status != BatchStatus.COMPLETED:
        raise HTTPException(409, "Simpan data unggahan terlebih dahulu")
    if review is None:
        raise HTTPException(404, "Acuan PDPJ tidak ditemukan")
    try:
        completed_review(db, review.batch_id, review_id)
        sources = pin_pipeline_sources(db, None, None, review.batch_id, batch_id, pdpj_review_id=review_id, correction_category=batch.dataset_type.value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    target_policy = COORDINATE_IDPEL_POLICY if batch.dataset_type == DatasetType.IDPEL_TIDAK_KETEMU else None
    # Reuse only analyses whose frozen source interpretation and rules agree.
    for item, process in db.query(RadiusAnalysis, ReconciliationProcess).join(
        ReconciliationProcess, ReconciliationProcess.id == RadiusAnalysis.process_id
    ).filter(RadiusAnalysis.batch_id == batch_id, RadiusAnalysis.pdpj_review_id == review_id).order_by(RadiusAnalysis.id.desc()).all():
        if process.source_batches == sources and item.progress.get(TARGET_POLICY_KEY) == target_policy:
            return item
    process = ReconciliationProcess(process_name=f"Analisis radius {batch.dataset_type.value.replace('_', ' ')}", target_batch_id=batch_id, source_batches=sources)
    db.add(process)
    db.flush()
    item = RadiusAnalysis(batch_id=batch_id, pdpj_review_id=review_id, process_id=process.id, actor=actor, request_key=request_key, progress={TARGET_POLICY_KEY: target_policy} if target_policy else {}, total_rows=db.query(SourceRecord.id).filter_by(batch_id=batch_id).count())
    db.add(item)
    db.commit()
    return item


def nearest_eligible(db: Session, snapshot_id: int, lat: float, lon: float) -> tuple[float, str, int] | None:
    # Use the existing snapshot/latitude index; don't load millions of observations.
    for radius in (25.0, 100.0, 400.0, 1600.0, 6400.0, 25600.0, MAX_RADIUS):
        query = db.query(CorrectionMasterObservation, MasterSisaRecord.idpel).join(
            MasterSisaRecord, MasterSisaRecord.id == CorrectionMasterObservation.master_record_id
        ).filter(
            CorrectionMasterObservation.snapshot_id == snapshot_id,
            MasterSisaRecord.snapshot_id == snapshot_id,
            observation_window(lat, lon, radius),
        )
        best = None
        for observation, idpel in query.yield_per(1000):
            distance = calculate_haversine_distance(lat, lon, observation.latitude, observation.longitude)
            candidate = (distance, idpel, observation.source_record_id)
            if distance <= radius and (best is None or candidate < best):
                best = candidate
        if best is not None:
            return best
    return None


def advance_analysis(db: Session, analysis_id: int, revision: int, chunk_size: int = 20) -> RadiusAnalysis:
    item = get_analysis(db, analysis_id, locked=True)
    if item.revision != revision:
        raise HTTPException(409, "Progres berubah. Muat ulang analisis sebelum melanjutkan")
    if item.state == "ready":
        return item
    if item.state != "running":
        raise HTTPException(409, "Lanjutkan analisis yang dijeda terlebih dahulu")
    process = db.get(ReconciliationProcess, item.process_id)
    assert process is not None
    started = monotonic()
    try:
        if item.stage == "preparing":
            preparation = advance_preparation(db, process, item.progress.get("preparation"))
            if preparation["phase"] == "ready":
                observations = advance_observations(db, process)
                if not observations["ready"]:
                    preparation = {**preparation, "phase": "observations"}
                else:
                    item.stage = "analyzing"
                preparation["observations"] = observations
            item.progress = {**item.progress, "preparation": preparation}
        else:
            batch = db.get(UploadBatch, item.batch_id)
            assert batch is not None and process.master_snapshot_id is not None
            rows = db.query(SourceRecord).filter(SourceRecord.batch_id == item.batch_id, SourceRecord.id > item.last_source_id).order_by(SourceRecord.id).limit(max(1, min(chunk_size, 100))).all()
            coordinate_only = item.progress.get(TARGET_POLICY_KEY) == COORDINATE_IDPEL_POLICY
            parsed_fields = [extract_standard_fields(source.data or {}, batch.column_mapping) for source in rows]
            context = None
            if batch.dataset_type == DatasetType.IDPEL_TIDAK_KETEMU and rows:
                review = db.get(PdpjReview, item.pdpj_review_id)
                assert review is not None
                context = chunk_context(db, review, parsed_fields, [source.data or {} for source in rows], batch, identities_only=coordinate_only)
            for source, fields in zip(rows, parsed_fields):
                errors = target_errors(validate_fields(fields, batch.dataset_type), batch.dataset_type, coordinate_only=coordinate_only)
                coordinate_errors = any(error["field"] in {"lat", "lon"} for error in errors)
                issue = "invalid_data" if coordinate_errors else "missing_coordinates" if fields["lat"] is None or fields["lon"] is None else "invalid_category" if errors else None
                if context is not None:
                    from app.modules.corrections.service import reference_tokens
                    if fields.get("idpel") in context.identities:
                        issue = "idpel_in_pdpj"
                    elif not coordinate_only and any((key, value) in context.references for key, values in reference_tokens(fields, source.data or {}, batch.column_mapping).items() for value in values):
                        issue = "reference_conflict"
                nearest = None if issue else nearest_eligible(db, process.master_snapshot_id, fields["lat"], fields["lon"])
                if issue is None and nearest is None:
                    issue = "outside_limit"
                db.add(RadiusAnalysisRow(analysis_id=item.id, source_record_id=source.id, distance_meters=nearest[0] if nearest else None, candidate_idpel=nearest[1] if nearest else None, observation_source_id=nearest[2] if nearest else None, issue=issue))
                item.last_source_id = source.id
                item.processed_rows += 1
            if not rows and item.processed_rows != item.total_rows:
                raise ValueError("Source rows changed during analysis")
            if item.processed_rows == item.total_rows:
                item.stage, item.state = "done", "ready"
                process.matching_status = ProcessStatus.COMPLETED
        item.revision += 1
        item.progress = {**item.progress, "elapsed_seconds": item.progress.get("elapsed_seconds", 0.0) + monotonic() - started}
        item.updated_at = utc_now()
        db.commit()
        return item
    except Exception:
        db.rollback()
        item = get_analysis(db, analysis_id, locked=True)
        item.state = "failed"
        item.error = "Bagian aktif belum tersimpan. Lanjutkan dari hasil terakhir."
        item.revision += 1
        db.commit()
        raise


def analysis_info(db: Session, item: RadiusAnalysis, radius: float | None = None) -> dict[str, Any]:
    query = db.query(RadiusAnalysisRow).filter_by(analysis_id=item.id)
    found = query.filter(RadiusAnalysisRow.distance_meters.is_not(None))
    found_count = found.count()
    uncovered = query.filter_by(issue="outside_limit").count()
    coordinates = query.filter(RadiusAnalysisRow.issue.in_(["invalid_data", "missing_coordinates"])).count()
    category = query.filter_by(issue="invalid_category").count()
    idpel_in_pdpj = query.filter_by(issue="idpel_in_pdpj").count()
    reference_conflicts = query.filter_by(issue="reference_conflict").count()
    invalid = coordinates + category + idpel_in_pdpj + reference_conflicts
    maximum = found.with_entities(func.max(RadiusAnalysisRow.distance_meters)).scalar()
    recommendation = max(5, math.ceil(maximum / 5) * 5) if maximum is not None else None
    complete = item.state == "ready"
    farthest = found.join(SourceRecord, SourceRecord.id == RadiusAnalysisRow.source_record_id).with_entities(SourceRecord.row_number, RadiusAnalysisRow.distance_meters).order_by(RadiusAnalysisRow.distance_meters.desc()).limit(5).all()
    return {
        "id": item.id, "batch_id": item.batch_id, "pdpj_review_id": item.pdpj_review_id, "actor": item.actor,
        "state": item.state, "stage": item.stage, "revision": item.revision,
        "total_rows": item.total_rows, "processed_rows": item.processed_rows,
        "eligible_rows": found_count + uncovered, "invalid_rows": invalid,
        "coordinate_rows": coordinates, "category_rows": category,
        "idpel_in_pdpj_rows": idpel_in_pdpj, "reference_conflict_rows": reference_conflicts,
        "elapsed_seconds": item.progress.get("elapsed_seconds", 0.0),
        "covered_rows": found_count, "outside_limit_rows": uncovered,
        "recommended_radius_meters": recommendation if complete and not uncovered else None,
        "partial_radius_meters": recommendation if complete else None,
        "max_analysis_radius_meters": MAX_RADIUS,
        "selected_radius_meters": item.progress.get("selected_radius_meters"),
        "coverage_rows": found.filter(RadiusAnalysisRow.distance_meters <= radius).count() if radius is not None else None,
        "farthest_rows": [{"row_number": number, "distance_meters": distance} for number, distance in farthest],
        "progress": item.progress, "error": item.error,
    }
