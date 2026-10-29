import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.correction import CorrectionCheck
from app.models.matching import MatchCandidate, MatchingRun, ReconciliationProcess
from app.modules.corrections.results import export_results, results_summary
from app.modules.corrections.service import CorrectionKind
from app.modules.corrections.spreadsheet import Spreadsheet

DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(tags=["History & Result"])


@router.get("/history/processes")
def get_process_history(db: DbSession):
    """Mengambil seluruh riwayat proses yang pernah dijalankan (PRD §8 FR-HIST-01)"""
    processes = (
        db.query(ReconciliationProcess)
        .order_by(ReconciliationProcess.created_at.desc())
        .all()
    )
    result = []
    for p in processes:
        result.append(
            {
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
            }
        )
    for item in result:
        check = db.get(CorrectionCheck, item["id"])
        if check is not None:
            item.update(
                results_summary(db, CorrectionKind(check.category), check.process_id)
            )
    return result


@router.delete("/history/processes/{process_id}")
def delete_process(process_id: int, db: DbSession):
    """Menghapus satu riwayat proses beserta semua kandidat hasil pencocokannya"""
    process = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.id == process_id)
        .first()
    )
    if not process:
        raise HTTPException(status_code=404, detail="Proses tidak ditemukan")

    try:
        # Hapus kandidat terkait terlebih dahulu (cascade fallback)
        db.query(MatchCandidate).filter(
            MatchCandidate.process_id == process_id
        ).delete()
        db.query(MatchingRun).filter(MatchingRun.process_id == process_id).delete()
        db.delete(process)
        db.commit()
        return {"message": f"Riwayat proses #{process_id} berhasil dihapus"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus riwayat: {e!s}")


@router.delete("/history/processes")
def clear_all_history(db: DbSession):
    """Menghapus semua riwayat proses rekonsiliasi"""
    try:
        db.query(MatchCandidate).delete()
        db.query(MatchingRun).delete()
        db.query(ReconciliationProcess).delete()
        db.commit()
        return {"message": "Semua riwayat proses rekonsiliasi berhasil dibersihkan"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Gagal membersihkan riwayat: {e!s}"
        )


def get_process_generation(
    db: Session, process_id: int, generation: int | None
) -> tuple:
    """An absent process or attempt never redirects to another process."""
    process = db.get(ReconciliationProcess, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Proses tidak ditemukan")
    selected = process.current_generation if generation is None else generation
    run = (
        db.query(MatchingRun)
        .filter(
            MatchingRun.process_id == process_id, MatchingRun.generation == selected
        )
        .first()
    )
    if generation is not None and run is None:
        raise HTTPException(status_code=404, detail="Versi pencarian tidak ditemukan")
    return process, selected, run


@router.get("/process/{process_id}/summary")
def get_process_summary(
    process_id: int, db: DbSession, generation: int | None = Query(None, ge=1)
) -> dict:
    """Read summary strictly within the requested process and search generation."""
    check = db.get(CorrectionCheck, process_id)
    if check is not None:
        return results_summary(
            db, CorrectionKind(check.category), process_id, generation
        )
    process, selected, run = get_process_generation(db, process_id, generation)
    candidates = (
        db.query(MatchCandidate)
        .filter(
            MatchCandidate.process_id == process_id,
            MatchCandidate.generation == selected,
        )
        .all()
    )
    return {
        "process_id": process.id,
        "generation": selected,
        "master_snapshot_id": process.master_snapshot_id,
        "process_name": process.process_name,
        "radius_meters": run.radius_meters if run else process.radius_meters or 0,
        "total_targets": run.total_targets if run else process.total_targets or 0,
        "total_candidates": len(candidates),
        "valid_count": sum(c.is_accepted == 1 for c in candidates),
        "rejected_count": sum(c.is_accepted == -1 for c in candidates),
        "pending_count": sum(c.is_accepted == 0 for c in candidates),
        "matching_status": run.status
        if generation is not None
        else process.matching_status,
        "review_status": process.review_status,
        "is_empty": False,
    }


@router.get("/process/{process_id}/export")
def export_process_results(
    process_id: int,
    db: DbSession,
    generation: int | None = Query(None, ge=1),
    format: Literal["csv", "xlsx"] = "csv",
) -> Response:
    """Export categorized results as XLSX; keep legacy CSV callers compatible."""
    check = db.get(CorrectionCheck, process_id)
    if check is not None:
        return export_results(
            db, CorrectionKind(check.category), process_id, generation
        )
    _, selected, _ = get_process_generation(db, process_id, generation)
    candidates = (
        db.query(MatchCandidate)
        .filter(
            MatchCandidate.process_id == process_id,
            MatchCandidate.generation == selected,
        )
        .order_by(MatchCandidate.target_ref, MatchCandidate.rank)
        .all()
    )
    if not candidates:
        raise HTTPException(
            status_code=404, detail="Tidak ada data kandidat untuk proses ini"
        )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header CSV Lengkap
    writer.writerow(
        [
            "TARGET_METER",
            "TARGET_LAT",
            "TARGET_LON",
            "KANDIDAT_IDPEL",
            "NAMA_PELANGGAN",
            "JENIS_LAYANAN",
            "JARAK_METER",
            "KLASIFIKASI_JARAK",
            "KELAYAKAN_DATA",
            "RANK",
            "STATUS_KEPUTUSAN",
            "GOOGLE_MAPS_URL",
        ]
    )

    for c in candidates:
        status_label = "PENDING"
        if c.is_accepted == 1:
            status_label = "VALID"
        elif c.is_accepted == -1:
            status_label = "DITOLAK"

        has_real_idpel = not (
            c.candidate_idpel.startswith("UNASSIGNED-") or not c.candidate_idpel
        )
        kelayakan = (
            "VALID (ADA IDPEL)" if has_real_idpel else "PERLU KONFIRMASI (TANPA IDPEL)"
        )
        klasifikasi_jarak = (
            "< 5 METER (RUMAH BERDAMPINGAN)" if c.distance_meters < 5.0 else "NORMAL"
        )
        gmaps_url = f"https://www.google.com/maps/search/?api=1&query={c.candidate_lat},{c.candidate_lon}"

        writer.writerow(
            [
                c.target_ref,
                c.target_lat,
                c.target_lon,
                c.candidate_idpel,
                c.candidate_nama,
                getattr(c, "jenis_layanan", "PASCABAYAR"),
                c.distance_meters,
                klasifikasi_jarak,
                kelayakan,
                c.rank,
                status_label,
                gmaps_url,
            ]
        )

    csv_data = output.getvalue()
    if format == "xlsx":
        book = Spreadsheet()
        rows = csv.reader(io.StringIO(csv_data))
        headers = next(rows)
        sheet = book.sheet("Hasil Rekonsiliasi", headers, [26] * len(headers))
        for row in rows:
            book.append(sheet, row)
        return book.response(f"hasil_geomatch_proses_{process_id}.xlsx")
    filename = f"hasil_geomatch_proses_{process_id}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
