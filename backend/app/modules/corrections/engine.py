"""Find PDPJ conflicts first, then persist every real candidate within the requested radius."""

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from typing import Any, cast

from sqlalchemy.orm import Session

from app.models.correction import (
    CorrectionCandidateEvidence,
    CorrectionCheck,
    CorrectionTarget,
    utc_now,
)
from app.models.master_sisa import MasterSisaRecord
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from app.models.pdpj import PdpjRow
from app.models.upload import BatchStatus, SourceRecord, UploadBatch
from app.modules.corrections.service import CORRECTION_TYPES, reference_tokens
from app.modules.pdpj.service import completed_review
from app.modules.spatial.engine import (
    calculate_haversine_distance,
    lock_matching_session,
    matching_run_summary,
)
from app.modules.upload.normalization import (
    extract_standard_fields,
    validate_fields,
    with_reference_fields,
)


def run_correction_matching(
    db: Session, process_id: int, target_batch_id: int, run_id: int | None
) -> dict[str, Any]:
    """Publish target outcomes and candidates together, preserving prior generations."""
    lock_matching_session(db)
    process = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.id == process_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    check = db.get(CorrectionCheck, process_id)
    batch = db.get(UploadBatch, target_batch_id)
    if (
        process is None
        or check is None
        or batch is None
        or batch.dataset_type not in CORRECTION_TYPES
        or batch.status != BatchStatus.COMPLETED
        or process.target_batch_id != target_batch_id
        or check.category != batch.dataset_type.value
    ):
        raise ValueError(
            "Sumber pemeriksaan koreksi tidak sesuai; gunakan menu Data Koreksi"
        )
    pdpj_id = (process.source_batches or {}).get("pdpj")
    if pdpj_id is None:
        raise ValueError("Sumber PDPJ pemeriksaan belum disimpan")
    review = completed_review(db, pdpj_id, check.pdpj_review_id)
    run = (
        db.query(MatchingRun)
        .filter(MatchingRun.id == run_id, MatchingRun.process_id == process_id)
        .with_for_update()
        .first()
    )
    if run is None or process.master_snapshot_id is None:
        raise ValueError("Versi pemeriksaan atau snapshot master belum disiapkan")
    if run.status == ProcessStatus.COMPLETED:
        return matching_run_summary(db, process, run)
    latest = (
        db.query(MatchingRun.id)
        .filter(MatchingRun.process_id == process_id)
        .order_by(MatchingRun.generation.desc())
        .limit(1)
        .scalar()
    )
    if run.generation <= process.current_generation or run.id != latest:
        raise ValueError("Pemeriksaan ini telah digantikan versi yang lebih baru")
    run.status = process.matching_status = ProcessStatus.RUNNING
    run.failure_code = None
    pdpj_batch = db.get(UploadBatch, review.batch_id)
    assert pdpj_batch is not None
    identities: dict[str, list[dict[str, Any]]] = defaultdict(list)
    references: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    coordinates: dict[tuple[float, float], list[int]] = defaultdict(list)
    for row, source in (
        db.query(PdpjRow, SourceRecord)
        .join(SourceRecord, SourceRecord.id == PdpjRow.source_record_id)
        .filter(PdpjRow.review_id == review.id)
        .yield_per(400)
    ):
        # Older reviews predate typed reference fields; preserve their approved
        # values while deriving recognizable reference types from original headers.
        fields = with_reference_fields(
            row.current_fields, source.data or {}, pdpj_batch.column_mapping
        )
        evidence = {
            "pdpj_row_id": row.id,
            "row_number": row.row_number,
            "fields": fields,
        }
        if fields.get("idpel"):
            identities[fields["idpel"]].append(evidence)
        for kind, values in reference_tokens(
            fields, source.data or {}, pdpj_batch.column_mapping
        ).items():
            for value in values:
                references[(kind, value)].append(evidence)
        if fields.get("lat") is not None and fields.get("lon") is not None:
            coordinates[(round(fields["lat"], 7), round(fields["lon"], 7))].append(
                row.row_number
            )
    master_ids = {
        value
        for (value,) in db.query(SourceRecord.idpel)
        .filter(
            SourceRecord.batch_id.in_(review.master_batch_ids),
            SourceRecord.idpel.isnot(None),
        )
        .distinct()
        .yield_per(400)
    }
    eligible = (
        db.query(MasterSisaRecord)
        .filter(
            MasterSisaRecord.snapshot_id == process.master_snapshot_id,
            MasterSisaRecord.latitude.isnot(None),
            MasterSisaRecord.longitude.isnot(None),
        )
        .order_by(MasterSisaRecord.latitude, MasterSisaRecord.id)
        .all()
    )
    records = (
        db.query(SourceRecord)
        .filter(SourceRecord.batch_id == target_batch_id)
        .order_by(SourceRecord.id)
        .all()
    )
    matched = 0
    # A latitude band is a conservative spherical bound. Full source snapshots
    # are loaded only for real candidates, then reused across nearby targets.
    latitudes = [cast(float, master.latitude) for master in eligible]
    latitude_delta = math.degrees(run.radius_meters / 6371000) + 1e-9
    source_cache: dict[int, SourceRecord] = {}
    for index, record in enumerate(records):
        # Conflict-only targets never reach the candidate flush below. Bound
        # pending outcomes as well, while publishing the generation in one commit.
        if index and index % 100 == 0:
            db.flush()
        fields = extract_standard_fields(record.data or {}, batch.column_mapping)
        errors = validate_fields(fields, batch.dataset_type)
        fields.pop("validation_errors", None)
        identity = (
            "empty"
            if not fields["idpel"]
            else "invalid"
            if any(
                error["field"] == "idpel"
                and error["code"] == "format_idpel_tidak_valid"
                for error in errors
            )
            else "found"
            if fields["idpel"] in master_ids
            else "not_found"
        )
        conflicts = [
            {"code": "idpel_sama_pdpj", "value": fields["idpel"], **item}
            for item in identities.get(fields["idpel"], [])
        ]
        for kind, values in reference_tokens(
            fields, record.data or {}, batch.column_mapping
        ).items():
            for value in sorted(values):
                conflicts.extend(
                    {"code": f"{kind}_sama_pdpj", "value": value, **item}
                    for item in references.get((kind, value), [])
                )
        lat, lon = fields["lat"], fields["lon"]
        warnings = []
        if (
            lat is not None
            and lon is not None
            and (same := coordinates.get((round(lat, 7), round(lon, 7))))
        ):
            warnings.append({"code": "koordinat_sama_pdpj", "pdpj_rows": same})
        status = (
            "pdpj_conflict"
            if conflicts
            else "invalid_data"
            if errors
            else "incomplete_coordinates"
            if lat is None or lon is None
            else "no_candidates"
        )
        outcome = CorrectionTarget(
            run_id=run.id,
            source_record_id=record.id,
            fields=fields,
            identity_status=identity,
            search_status=status,
            errors=errors,
            conflicts=conflicts,
            warnings=warnings,
        )
        db.add(outcome)
        if status != "no_candidates":
            continue
        found = []
        lower = bisect_left(latitudes, lat - latitude_delta)
        upper = bisect_right(latitudes, lat + latitude_delta)
        for master in eligible[lower:upper]:
            if (
                master.idpel in identities
                or master.latitude is None
                or master.longitude is None
            ):
                continue
            distance = calculate_haversine_distance(
                lat, lon, master.latitude, master.longitude
            )
            if distance <= run.radius_meters:
                if master.source_record_id is None:
                    continue
                source = source_cache.get(master.source_record_id) or db.get(
                    SourceRecord, master.source_record_id
                )
                if source is None:
                    continue
                source_cache[master.source_record_id] = source
                found.append((distance, master.idpel, master, source))
        found.sort(key=lambda item: (item[0], item[1]))
        for rank, (distance, _, master, source) in enumerate(found, 1):
            candidate = MatchCandidate(
                process_id=process_id,
                generation=run.generation,
                target_record_id=record.id,
                target_ref=fields["target_ref"]
                or fields["idpel"]
                or f"TARGET-{record.id}",
                target_lat=lat,
                target_lon=lon,
                candidate_idpel=master.idpel,
                candidate_nama=master.nama,
                candidate_lat=master.latitude,
                candidate_lon=master.longitude,
                distance_meters=round(distance, 2),
                rank=rank,
                jenis_layanan=master.jenis_layanan,
                validity_status="VALID",
                is_under_5m=int(distance < 5),
                is_accepted=0,
            )
            db.add(candidate)
            db.flush()
            db.add(
                CorrectionCandidateEvidence(
                    candidate_id=candidate.id,
                    master_record_id=master.id,
                    fields={
                        key: value
                        for key, value in (source.data or {}).items()
                        if key != "source_observations"
                    },
                    observations=(source.data or {}).get("source_observations", []),
                )
            )
        outcome.candidate_count = len(found)
        if found:
            outcome.search_status = "matched"
            matched += 1
    run.status = process.matching_status = ProcessStatus.COMPLETED
    run.total_targets = process.total_targets = len(records)
    run.matched_targets = process.matched_targets = matched
    process.unmatched_targets = len(records) - matched
    process.current_generation = run.generation
    process.radius_meters = run.radius_meters
    process.review_status = ReviewStatus.IN_PROGRESS
    run.completed_at = process.completed_at = utc_now()
    db.commit()
    return matching_run_summary(db, process, run)
