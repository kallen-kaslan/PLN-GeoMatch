"""Versioned spatial matching against a process-bound master snapshot."""

import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.master_sisa import MasterSisaRecord
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.spatial.preparation import resolve_master_snapshot
from app.modules.upload.normalization import extract_standard_fields


def lock_matching_session(db: Session) -> None:
    """SQLite serializes writers; PostgreSQL uses the process row locks below."""
    if db.get_bind().dialect.name == "sqlite":
        connection = db.connection()
        driver_connection = connection.connection.driver_connection
        assert driver_connection is not None
        if not driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Return the great-circle distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlon / 2) ** 2
    )
    return 6371000 * 2 * math.atan2(math.sqrt(min(1, a)), math.sqrt(max(0, 1 - a)))


def validate_target_batch(db: Session, batch_id: int) -> UploadBatch:
    """Only explicitly mapped, completed target batches can be matched."""
    batch = db.get(UploadBatch, batch_id)
    if batch is None or batch.dataset_type not in {
        DatasetType.TARGET,
        DatasetType.KOORDINAT_KOSONG,
    }:
        raise ValueError("Batch target tidak ditemukan atau jenisnya tidak sesuai")
    if batch.status != BatchStatus.COMPLETED:
        raise ValueError("Konfirmasi mapping dan validasi batch target terlebih dahulu")
    return batch


def create_matching_run(
    db: Session,
    process: ReconciliationProcess,
    radius_meters: float,
    max_candidates: int,
) -> MatchingRun:
    """Reserve a new generation; publishing happens atomically after matching."""
    lock_matching_session(db)
    if (
        not math.isfinite(radius_meters)
        or radius_meters <= 0
        or not 1 <= max_candidates <= 1000
    ):
        raise ValueError(
            "Radius harus positif dan jumlah kandidat antara 1 sampai 1000"
        )
    process = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.id == process.id)
        .populate_existing()
        .with_for_update()
        .one()
    )
    if process.master_snapshot_id is None or process.target_batch_id is None:
        raise ValueError(
            "Sumber proses lama tidak tercatat; buat proses baru dengan snapshot yang dipilih"
        )
    resolve_master_snapshot(db, process.master_snapshot_id)
    validate_target_batch(db, process.target_batch_id)
    pending = (
        db.query(MatchingRun)
        .filter(
            MatchingRun.process_id == process.id,
            MatchingRun.status.in_([ProcessStatus.QUEUED, ProcessStatus.RUNNING]),
        )
        .first()
    )
    if pending:
        raise ValueError("Masih ada pencarian yang sedang berjalan untuk proses ini")
    latest = (
        db.query(func.max(MatchingRun.generation))
        .filter(MatchingRun.process_id == process.id)
        .scalar()
    )
    run = MatchingRun(
        process_id=process.id,
        generation=max(latest or 0, process.current_generation or 0) + 1,
        radius_meters=radius_meters,
        max_candidates=max_candidates,
        status=ProcessStatus.QUEUED,
    )
    db.add(run)
    process.matching_status = ProcessStatus.QUEUED
    db.flush()
    return run


def matching_run_summary(
    db: Session, process: ReconciliationProcess, run: MatchingRun
) -> dict[str, Any]:
    """Read one attempt without switching the active process or generation."""
    count = (
        db.query(MatchCandidate)
        .filter(
            MatchCandidate.process_id == process.id,
            MatchCandidate.generation == run.generation,
        )
        .count()
    )
    return {
        "process_id": process.id,
        "process_name": process.process_name,
        "run_id": run.id,
        "generation": run.generation,
        "master_snapshot_id": process.master_snapshot_id,
        "total_targets": run.total_targets,
        "matched_targets": run.matched_targets,
        "unmatched_targets": run.total_targets - run.matched_targets,
        "total_candidates_found": count,
        "status": run.status.value,
    }


def run_spatial_matching_job(
    db: Session,
    process_name: str,
    target_batch_id: int,
    radius_meters: float = 100.0,
    max_candidates_per_target: int = 5,
    process_id: int | None = None,
    master_snapshot_id: int | None = None,
    run_id: int | None = None,
) -> dict[str, Any]:
    """Create a new attempt, or safely redeliver the same reserved run ID."""
    lock_matching_session(db)
    target = db.get(UploadBatch, target_batch_id)
    if target and target.dataset_type in {
        DatasetType.IDPEL_TIDAK_KETEMU,
        DatasetType.IDPEL_KOSONG,
    }:
        if process_id is None:
            raise ValueError("Buat pemeriksaan melalui menu Data Koreksi")
        from app.modules.corrections.engine import run_correction_matching

        return run_correction_matching(db, process_id, target_batch_id, run_id)
    target_batch = validate_target_batch(db, target_batch_id)
    process: ReconciliationProcess | None
    run: MatchingRun | None
    if process_id is None:
        snapshot = resolve_master_snapshot(db, master_snapshot_id)
        process = ReconciliationProcess(
            process_name=process_name,
            radius_meters=radius_meters,
            master_snapshot_id=snapshot.id,
            target_batch_id=target_batch_id,
            review_status=ReviewStatus.NOT_STARTED,
        )
        db.add(process)
        db.flush()
    else:
        process = (
            db.query(ReconciliationProcess)
            .filter(ReconciliationProcess.id == process_id)
            .with_for_update()
            .first()
        )
        if process is None:
            raise ValueError("Proses tidak ditemukan")
        if process.target_batch_id != target_batch_id:
            raise ValueError("Batch target tidak sesuai dengan sumber proses")
        if (
            master_snapshot_id is not None
            and process.master_snapshot_id != master_snapshot_id
        ):
            raise ValueError("Snapshot tidak sesuai dengan sumber proses")
    if run_id is None:
        run = create_matching_run(db, process, radius_meters, max_candidates_per_target)
    else:
        run = (
            db.query(MatchingRun)
            .filter(MatchingRun.id == run_id, MatchingRun.process_id == process.id)
            .with_for_update()
            .first()
        )
        if run is None:
            raise ValueError("Versi pencarian tidak ditemukan pada proses ini")
        if run.status == ProcessStatus.COMPLETED:
            return matching_run_summary(db, process, run)
        if run.generation <= process.current_generation:
            raise ValueError("Versi pencarian lama tidak boleh menimpa hasil aktif")
    # A single transaction writes candidates and publishes the completed generation.
    if run.max_candidates is None:
        raise ValueError("Parameter pencarian historis tidak lengkap; buat proses baru")
    run.status = ProcessStatus.RUNNING
    run.failure_code = None
    process.matching_status = ProcessStatus.RUNNING
    radius_meters, max_candidates_per_target = run.radius_meters, run.max_candidates
    target_records = (
        db.query(SourceRecord).filter(SourceRecord.batch_id == target_batch_id).all()
    )
    master_sisa = (
        db.query(MasterSisaRecord)
        .filter(
            MasterSisaRecord.snapshot_id == process.master_snapshot_id,
            MasterSisaRecord.latitude.isnot(None),
            MasterSisaRecord.longitude.isnot(None),
        )
        .all()
    )

    total_targets = len(target_records)
    matched_count = 0
    all_candidates: list[MatchCandidate] = []

    for t in target_records:
        fields = extract_standard_fields(t.data or {}, target_batch.column_mapping)
        t_lat, t_lon = fields["lat"], fields["lon"]
        if (
            not t.is_valid
            or fields["validation_errors"]
            or t_lat is None
            or t_lon is None
        ):
            continue
        t_ref = fields["target_ref"] or fields["idpel"] or f"TITIK-KOSONG-{t.id}"

        # 4. Cari kandidat di Master Sisa
        candidates_found: list[dict[str, Any]] = []
        closest_any = None
        min_dist_any = float("inf")

        for m in master_sisa:
            if m.latitude is None or m.longitude is None:
                continue
            dist = calculate_haversine_distance(t_lat, t_lon, m.latitude, m.longitude)
            if dist < min_dist_any:
                min_dist_any = dist
                closest_any = m

            if dist <= radius_meters:
                has_real_idpel = not (
                    m.idpel.startswith("UNASSIGNED-")
                    or not m.idpel
                    or m.idpel.strip() == ""
                )
                # IDPEL_KOSONG = IDPEL kosong/tidak ada (prioritas utama)
                is_idpel_kosong = not m.idpel or m.idpel.strip() == ""

                if is_idpel_kosong:
                    validity = "IDPEL_KOSONG"
                elif has_real_idpel:
                    validity = "VALID"
                else:
                    validity = "PERLU_KONFIRMASI_IDPEL"

                candidates_found.append(
                    {
                        "idpel": m.idpel
                        if m.idpel and m.idpel.strip()
                        else "IDPEL_KOSONG",
                        "nama": m.nama,
                        "lat": m.latitude,
                        "lon": m.longitude,
                        "dist": round(dist, 2),
                        "jenis_layanan": getattr(m, "jenis_layanan", "PASCABAYAR"),
                        "validity_status": validity,
                        "is_under_5m": 1 if dist < 5.0 else 0,
                    }
                )

        candidates_found.sort(key=lambda x: x["dist"])
        top_candidates = candidates_found[:max_candidates_per_target]

        if top_candidates:
            matched_count += 1
            for rank_idx, c in enumerate(top_candidates, 1):
                cand_obj = MatchCandidate(
                    process_id=process.id,
                    generation=run.generation,
                    target_record_id=t.id,
                    target_ref=t_ref,
                    target_lat=t_lat,
                    target_lon=t_lon,
                    candidate_idpel=c["idpel"],
                    candidate_nama=c["nama"],
                    candidate_lat=c["lat"],
                    candidate_lon=c["lon"],
                    distance_meters=c["dist"],
                    rank=rank_idx,
                    jenis_layanan=c["jenis_layanan"],
                    validity_status=c["validity_status"],
                    is_under_5m=c["is_under_5m"],
                    is_accepted=0,
                )
                all_candidates.append(cand_obj)
        else:
            # Tidak menemukan kandidat dalam radius -> Tetap jabarkan di tabel agar petugas bisa mereview seluruh titik lapangan
            cand_obj = MatchCandidate(
                process_id=process.id,
                generation=run.generation,
                target_record_id=t.id,
                target_ref=t_ref,
                target_lat=t_lat,
                target_lon=t_lon,
                candidate_idpel=f"DILUAR_RADIUS ({round(min_dist_any, 1)}m)"
                if closest_any
                else "TIDAK_DITEMUKAN",
                candidate_nama=f"Kandidat terdekat: {closest_any.nama}"
                if closest_any
                else "Tidak ada calon pelanggan",
                candidate_lat=closest_any.latitude if closest_any else t_lat,
                candidate_lon=closest_any.longitude if closest_any else t_lon,
                distance_meters=round(min_dist_any, 2) if closest_any else 0.0,
                rank=1,
                jenis_layanan=getattr(closest_any, "jenis_layanan", "-")
                if closest_any
                else "-",
                validity_status="DILUAR_RADIUS",
                is_under_5m=0,
                is_accepted=0,
            )
            all_candidates.append(cand_obj)

    if all_candidates:
        db.bulk_save_objects(all_candidates)

    run.status = ProcessStatus.COMPLETED
    run.total_targets = total_targets
    run.matched_targets = matched_count
    run.completed_at = datetime.now(UTC).replace(tzinfo=None)
    process.current_generation = run.generation
    process.radius_meters = run.radius_meters
    process.matching_status = ProcessStatus.COMPLETED
    process.review_status = ReviewStatus.IN_PROGRESS
    process.total_targets = total_targets
    process.matched_targets = matched_count
    process.unmatched_targets = total_targets - matched_count
    process.completed_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()

    return matching_run_summary(db, process, run)
