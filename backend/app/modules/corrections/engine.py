"""Find PDPJ conflicts first, then persist every real candidate within the requested radius."""

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Mapping
from time import monotonic
from typing import Any, cast

from sqlalchemy import false, or_
from sqlalchemy.orm import Session

from app.models.correction import CorrectionCheck, utc_now
from app.models.master_sisa import MasterSisaRecord
from app.models.matching import (
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from app.models.pdpj import PdpjRow
from app.models.upload import BatchStatus, SourceRecord, UploadBatch
from app.modules.corrections.pdpj_index import chunk_context
from app.modules.corrections.service import CORRECTION_TYPES, reference_tokens
from app.modules.corrections.writer import SearchWriter
from app.modules.pdpj.service import completed_review, pending_pdpj_records
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
from app.performance import timed


@timed("corrections.match_and_store")
def run_correction_matching(
    db: Session,
    process_id: int,
    target_batch_id: int,
    run_id: int | None,
    *,
    chunk_size: int | None = None,
) -> dict[str, Any]:
    """Publish target outcomes and candidates together, preserving prior generations."""
    started = monotonic()
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
    progress = (
        dict(run.processing) if chunk_size is not None and run.processing else None
    )
    records_query = (
        db.query(SourceRecord)
        .filter(SourceRecord.batch_id == target_batch_id)
        .order_by(SourceRecord.id)
    )
    records = (
        records_query.filter(SourceRecord.id > progress["last_source_id"])
        .limit(chunk_size)
        .all()
        if progress
        else records_query.yield_per(100)
    )
    target_fields = (
        [
            extract_standard_fields(record.data or {}, batch.column_mapping)
            for record in records
        ]
        if progress
        else []
    )
    identities: Mapping[str, list[dict[str, Any]]]
    references: Mapping[tuple[str, str], list[dict[str, Any]]]
    coordinates: dict[tuple[float, float], list[int]]
    if progress:
        context = chunk_context(
            db, review, target_fields, [record.data or {} for record in records], batch
        )
        identities, references, coordinates = (
            context.identities,
            context.references,
            context.coordinates,
        )
    else:
        pdpj_batch = db.get(UploadBatch, review.batch_id)
        assert pdpj_batch is not None
        identities = defaultdict(list)
        references = defaultdict(list)
        coordinates = defaultdict(list)
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
        # Pending source identities/references are reserved in this version too.
        # Their evidence is explicitly marked as awaiting PDPJ validation.
        for source in pending_pdpj_records(db, review):
            fields = extract_standard_fields(
                source.data or {}, pdpj_batch.column_mapping
            )
            evidence = {
                "pdpj_row_id": None,
                "row_number": source.row_number,
                "fields": fields,
                "pending_validation": True,
            }
            if fields.get("idpel"):
                identities[fields["idpel"]].append(evidence)
            for kind, values in reference_tokens(
                fields, source.data or {}, pdpj_batch.column_mapping
            ).items():
                for value in values:
                    references[(kind, value)].append(evidence)
    master_identity_query = db.query(SourceRecord.idpel).filter(
        SourceRecord.batch_id.in_(review.master_batch_ids),
        SourceRecord.idpel.isnot(None),
    )
    if progress:
        master_identity_query = master_identity_query.filter(
            SourceRecord.idpel.in_(
                {fields["idpel"] for fields in target_fields if fields["idpel"]}
            )
        )
    master_ids = {value for (value,) in master_identity_query.distinct().yield_per(400)}
    eligible_query = (
        db.query(MasterSisaRecord)
        .join(SourceRecord, SourceRecord.id == MasterSisaRecord.source_record_id)
        .filter(
            MasterSisaRecord.snapshot_id == process.master_snapshot_id,
            MasterSisaRecord.latitude.isnot(None),
            MasterSisaRecord.longitude.isnot(None),
        )
        .order_by(MasterSisaRecord.latitude, MasterSisaRecord.id)
    )
    latitude_delta = math.degrees(run.radius_meters / 6371000) + 1e-9
    if progress:
        # Use the existing snapshot/latitude index instead of loading the entire
        # master again for each checkpoint. The exact distance check stays below.
        target_latitudes = {
            fields["lat"]
            for fields in target_fields
            if fields["lat"] is not None and fields["lon"] is not None
        }
        eligible_query = eligible_query.filter(
            or_(
                *(
                    MasterSisaRecord.latitude.between(
                        latitude - latitude_delta, latitude + latitude_delta
                    )
                    for latitude in target_latitudes
                )
            )
            if target_latitudes
            else false()
        )
    eligible = eligible_query.all()
    matched = progress["matched_rows"] if progress else 0
    total_targets = progress["processed_rows"] if progress else 0
    last_source_id, last_row_number = 0, None
    writer = SearchWriter(db)
    # A latitude band is a conservative spherical bound. Full source snapshots
    # are loaded only for real candidates, then reused across nearby targets.
    latitudes = [cast(float, master.latitude) for master in eligible]
    for record in records:
        total_targets += 1
        last_source_id, last_row_number = record.id, record.row_number
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
        outcome = {
            "run_id": run.id,
            "source_record_id": record.id,
            "fields": fields,
            "identity_status": identity,
            "search_status": status,
            "candidate_count": 0,
            "errors": errors,
            "conflicts": conflicts,
            "warnings": warnings,
        }
        if status != "no_candidates":
            writer.outcome(outcome)
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
                found.append((distance, master.idpel, master))
        found.sort(key=lambda item: (item[0], item[1]))
        for rank, (distance, _, master) in enumerate(found, 1):
            candidate = {
                "process_id": process_id,
                "generation": run.generation,
                "target_record_id": record.id,
                "target_ref": fields["target_ref"]
                or fields["idpel"]
                or f"TARGET-{record.id}",
                "target_lat": lat,
                "target_lon": lon,
                "candidate_idpel": master.idpel,
                "candidate_nama": master.nama,
                "candidate_lat": master.latitude,
                "candidate_lon": master.longitude,
                "distance_meters": round(distance, 2),
                "rank": rank,
                "jenis_layanan": master.jenis_layanan,
                "validity_status": "VALID",
                "is_under_5m": int(distance < 5),
                "is_accepted": 0,
            }
            writer.candidate(candidate, master.id, cast(int, master.source_record_id))
        outcome["candidate_count"] = len(found)
        if found:
            outcome["search_status"] = "matched"
            matched += 1
        writer.outcome(outcome)
    writer.flush()
    if progress is not None:
        spent = monotonic() - started
        if last_source_id:
            progress.update(
                last_source_id=last_source_id, last_row_number=last_row_number
            )
        elif total_targets != progress["total_rows"]:
            raise ValueError("Jumlah baris koreksi tidak sesuai checkpoint")
        progress.update(
            processed_rows=total_targets,
            matched_rows=matched,
            elapsed_seconds=progress["elapsed_seconds"] + spent,
            stage_elapsed_seconds=progress.get("stage_elapsed_seconds", 0.0) + spent,
            stage_timed_rows=progress.get("stage_timed_rows", 0)
            + total_targets
            - progress["processed_rows"],
            updated_at=utc_now().isoformat(),
            revision=progress["revision"] + 1,
        )
        if total_targets == progress["total_rows"]:
            progress["stage"] = "validating"
            progress["stage_elapsed_seconds"] = 0.0
            progress["stage_timed_rows"] = 0
        run.processing = progress
        run.total_targets, run.matched_targets = progress["total_rows"], matched
        db.commit()
        return {"process_id": process_id, "status": "running"}
    run.status = process.matching_status = ProcessStatus.COMPLETED
    run.total_targets = process.total_targets = total_targets
    run.matched_targets = process.matched_targets = matched
    process.unmatched_targets = total_targets - matched
    process.current_generation = run.generation
    process.radius_meters = run.radius_meters
    process.review_status = ReviewStatus.IN_PROGRESS
    run.completed_at = process.completed_at = utc_now()
    db.commit()
    return matching_run_summary(db, process, run)
