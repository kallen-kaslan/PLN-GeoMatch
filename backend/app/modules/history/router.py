from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import io
import csv

from app.database import get_db
from app.models.matching import ReconciliationProcess, MatchCandidate

router = APIRouter(tags=["History & Result"])

@router.get("/history/processes")
async def get_process_history(db: Session = Depends(get_db)):
    """Mengambil seluruh riwayat proses yang pernah dijalankan (PRD §8 FR-HIST-01)"""
    processes = db.query(ReconciliationProcess).order_by(ReconciliationProcess.created_at.desc()).all()
    result = []
    for p in processes:
        result.append({
            "id": p.id,
            "process_name": p.process_name,
            "radius_meters": p.radius_meters,
            "matching_status": p.matching_status,
            "review_status": p.review_status,
            "total_targets": p.total_targets,
            "matched_targets": p.matched_targets,
            "unmatched_targets": p.unmatched_targets,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        })
    return result

@router.delete("/history/processes/{process_id}")
async def delete_process(process_id: int, db: Session = Depends(get_db)):
    """Menghapus satu riwayat proses beserta semua kandidat hasil pencocokannya"""
    process = db.query(ReconciliationProcess).filter(ReconciliationProcess.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="Proses tidak ditemukan")

    try:
        # Hapus kandidat terkait terlebih dahulu (cascade fallback)
        db.query(MatchCandidate).filter(MatchCandidate.process_id == process_id).delete()
        db.delete(process)
        db.commit()
        return {"message": f"Riwayat proses #{process_id} berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus riwayat: {str(e)}")

@router.delete("/history/processes")
async def clear_all_history(db: Session = Depends(get_db)):
    """Menghapus semua riwayat proses rekonsiliasi"""
    try:
        db.query(MatchCandidate).delete()
        db.query(ReconciliationProcess).delete()
        db.commit()
        return {"message": "Semua riwayat proses rekonsiliasi berhasil dibersihkan"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal membersihkan riwayat: {str(e)}")

@router.get("/process/{process_id}/summary")
async def get_process_summary(process_id: int, db: Session = Depends(get_db)):
    """Statistik hasil per proses (PRD §8 FR-RES-01)"""
    try:
        process = db.query(ReconciliationProcess).filter(ReconciliationProcess.id == process_id).first()

        # Jika ID yang dicari tidak ada, coba ambil proses terakhir yang ada
        if not process:
            process = db.query(ReconciliationProcess).order_by(ReconciliationProcess.id.desc()).first()
            if not process:
                return {
                    "process_id": process_id,
                    "process_name": "Belum ada proses yang dijalankan",
                    "radius_meters": 0,
                    "total_targets": 0,
                    "total_candidates": 0,
                    "valid_count": 0,
                    "rejected_count": 0,
                    "pending_count": 0,
                    "matching_status": "none",
                    "review_status": "none",
                    "is_empty": True
                }

        candidates = db.query(MatchCandidate).filter(MatchCandidate.process_id == process.id).all()

        valid_count = sum(1 for c in candidates if c.is_accepted == 1)
        rejected_count = sum(1 for c in candidates if c.is_accepted == -1)
        pending_count = sum(1 for c in candidates if c.is_accepted == 0)

        match_status_val = process.matching_status.value if hasattr(process.matching_status, "value") else str(process.matching_status)
        review_status_val = process.review_status.value if hasattr(process.review_status, "value") else str(process.review_status)

        return {
            "process_id": process.id,
            "process_name": process.process_name,
            "radius_meters": process.radius_meters or 0,
            "total_targets": process.total_targets or 0,
            "total_candidates": len(candidates),
            "valid_count": valid_count,
            "rejected_count": rejected_count,
            "pending_count": pending_count,
            "matching_status": match_status_val,
            "review_status": review_status_val,
            "is_empty": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil ringkasan proses: {str(e)}")

@router.get("/process/{process_id}/export")
async def export_process_results(process_id: int, db: Session = Depends(get_db)):
    """Ekspor hasil verifikasi ke file CSV (PRD §8 FR-RES-04)"""
    candidates = db.query(MatchCandidate).filter(MatchCandidate.process_id == process_id).all()
    if not candidates:
        raise HTTPException(status_code=404, detail="Tidak ada data kandidat untuk proses ini")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header CSV Lengkap
    writer.writerow([
        "TARGET_METER", "TARGET_LAT", "TARGET_LON",
        "KANDIDAT_IDPEL", "NAMA_PELANGGAN", "JENIS_LAYANAN", "JARAK_METER",
        "KLASIFIKASI_JARAK", "KELAYAKAN_DATA", "RANK", "STATUS_KEPUTUSAN", "GOOGLE_MAPS_URL"
    ])

    for c in candidates:
        status_label = "PENDING"
        if c.is_accepted == 1:
            status_label = "VALID"
        elif c.is_accepted == -1:
            status_label = "DITOLAK"

        has_real_idpel = not (c.candidate_idpel.startswith("UNASSIGNED-") or not c.candidate_idpel)
        kelayakan = "VALID (ADA IDPEL)" if has_real_idpel else "PERLU KONFIRMASI (TANPA IDPEL)"
        klasifikasi_jarak = "< 5 METER (RUMAH BERDAMPINGAN)" if c.distance_meters < 5.0 else "NORMAL"
        gmaps_url = f"https://www.google.com/maps/search/?api=1&query={c.candidate_lat},{c.candidate_lon}"

        writer.writerow([
            c.target_ref, c.target_lat, c.target_lon,
            c.candidate_idpel, c.candidate_nama, getattr(c, "jenis_layanan", "PASCABAYAR"),
            c.distance_meters, klasifikasi_jarak, kelayakan,
            c.rank, status_label, gmaps_url
        ])

    csv_data = output.getvalue()
    filename = f"hasil_geomatch_proses_{process_id}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
