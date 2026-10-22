import math
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.models.matching import ReconciliationProcess, MatchCandidate, ProcessStatus, ReviewStatus
from app.models.master_sisa import MasterSisaRecord
from app.models.upload import SourceRecord
from app.modules.spatial.master_builder import normalize_column_name

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def run_spatial_matching_job(
    db: Session,
    process_name: str,
    target_batch_id: int,
    radius_meters: float = 100.0,
    max_candidates_per_target: int = 5,
    process_id: int = None
) -> Dict[str, Any]:
    if process_id:
        process = db.query(ReconciliationProcess).filter(ReconciliationProcess.id == process_id).first()
        if not process:
            process = ReconciliationProcess(
                id=process_id,
                process_name=process_name,
                radius_meters=radius_meters,
                matching_status=ProcessStatus.RUNNING,
                review_status=ReviewStatus.NOT_STARTED,
            )
            db.add(process)
        else:
            process.matching_status = ProcessStatus.RUNNING
            process.radius_meters = radius_meters
    else:
        process = ReconciliationProcess(
            process_name=process_name,
            radius_meters=radius_meters,
            matching_status=ProcessStatus.RUNNING,
            review_status=ReviewStatus.NOT_STARTED,
        )
        db.add(process)
    db.commit()
    db.refresh(process)

    # Idempotensi: bersihkan kandidat lama dari proses ini jika ada (misal re-run atau retry)
    db.query(MatchCandidate).filter(MatchCandidate.process_id == process.id).delete()
    db.commit()

    target_records = db.query(SourceRecord).filter(SourceRecord.batch_id == target_batch_id).all()
    master_sisa = db.query(MasterSisaRecord).all()

    total_targets = len(target_records)
    matched_count = 0
    all_candidates: List[MatchCandidate] = []

    for t in target_records:
        t_data = t.data or {}
        normalized = {normalize_column_name(k): v for k, v in t_data.items() if v is not None}

        # 1. Ekstrak Latitude (Y) secara case-insensitive & robust
        t_lat = None
        for alias in ["latitudey", "latitude", "lat", "lintang", "koordinaty", "y"]:
            if alias in normalized:
                try:
                    val = float(str(normalized[alias]).replace(",", "."))
                    if val != 0:
                        t_lat = val
                        break
                except (ValueError, TypeError):
                    continue

        # 2. Ekstrak Longitude (X) secara case-insensitive & robust
        t_lon = None
        for alias in ["longitudex", "longitude", "long", "lon", "bujur", "koordinatx", "x"]:
            if alias in normalized:
                try:
                    val = float(str(normalized[alias]).replace(",", "."))
                    if val != 0:
                        t_lon = val
                        break
                except (ValueError, TypeError):
                    continue

        if t_lat is None or t_lon is None:
            continue

        # 3. Ekstrak Referensi Titik / No. Meter
        t_ref = None
        for alias in ["nomormeter", "nomor_meter", "notmeter", "idtitik", "noagenda", "ref", "idpelanggan", "idpel"]:
            if alias in normalized and str(normalized[alias]).strip():
                t_ref = str(normalized[alias]).strip()
                break
        if not t_ref:
            t_ref = f"TITIK-KOSONG-{t.id}"

        # 4. Cari kandidat di Master Sisa
        candidates_found = []
        closest_any = None
        min_dist_any = float("inf")

        for m in master_sisa:
            dist = calculate_haversine_distance(t_lat, t_lon, m.latitude, m.longitude)
            if dist < min_dist_any:
                min_dist_any = dist
                closest_any = m

            if dist <= radius_meters:
                has_real_idpel = not (m.idpel.startswith("UNASSIGNED-") or not m.idpel or m.idpel.strip() == "")
                # IDPEL_KOSONG = IDPEL kosong/tidak ada (prioritas utama)
                is_idpel_kosong = not m.idpel or m.idpel.strip() == ""

                if is_idpel_kosong:
                    validity = "IDPEL_KOSONG"
                elif has_real_idpel:
                    validity = "VALID"
                else:
                    validity = "PERLU_KONFIRMASI_IDPEL"

                candidates_found.append({
                    "idpel": m.idpel if m.idpel and m.idpel.strip() else "IDPEL_KOSONG",
                    "nama": m.nama,
                    "lat": m.latitude,
                    "lon": m.longitude,
                    "dist": round(dist, 2),
                    "jenis_layanan": getattr(m, "jenis_layanan", "PASCABAYAR"),
                    "validity_status": validity,
                    "is_under_5m": 1 if dist < 5.0 else 0
                })

        candidates_found.sort(key=lambda x: x["dist"])
        top_candidates = candidates_found[:max_candidates_per_target]

        if top_candidates:
            matched_count += 1
            for rank_idx, c in enumerate(top_candidates, 1):
                cand_obj = MatchCandidate(
                    process_id=process.id,
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
                    is_accepted=0
                )
                all_candidates.append(cand_obj)
        else:
            # Tidak menemukan kandidat dalam radius -> Tetap jabarkan di tabel agar petugas bisa mereview seluruh titik lapangan
            cand_obj = MatchCandidate(
                process_id=process.id,
                target_ref=t_ref,
                target_lat=t_lat,
                target_lon=t_lon,
                candidate_idpel=f"DILUAR_RADIUS ({round(min_dist_any, 1)}m)" if closest_any else "TIDAK_DITEMUKAN",
                candidate_nama=f"Kandidat terdekat: {closest_any.nama}" if closest_any else "Tidak ada calon pelanggan",
                candidate_lat=closest_any.latitude if closest_any else t_lat,
                candidate_lon=closest_any.longitude if closest_any else t_lon,
                distance_meters=round(min_dist_any, 2) if closest_any else 0.0,
                rank=1,
                jenis_layanan=getattr(closest_any, "jenis_layanan", "-") if closest_any else "-",
                validity_status="DILUAR_RADIUS",
                is_under_5m=0,
                is_accepted=0
            )
            all_candidates.append(cand_obj)

    if all_candidates:
        db.bulk_save_objects(all_candidates)

    process.matching_status = ProcessStatus.COMPLETED
    process.review_status = ReviewStatus.IN_PROGRESS
    process.total_targets = total_targets
    process.matched_targets = matched_count
    process.unmatched_targets = total_targets - matched_count
    process.completed_at = datetime.utcnow()
    db.commit()

    return {
        "process_id": process.id,
        "process_name": process.process_name,
        "total_targets": total_targets,
        "matched_targets": matched_count,
        "unmatched_targets": process.unmatched_targets,
        "total_candidates_found": len(all_candidates),
        "status": "completed"
    }
