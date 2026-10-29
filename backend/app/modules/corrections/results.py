"""Read saved correction choices, including partial runs and earlier search versions."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query as OrmQuery
from sqlalchemy.orm import Session, load_only, undefer
from sqlalchemy.sql.selectable import Subquery

from app.database import get_db
from app.models.correction import CorrectionCheck, CorrectionTarget
from app.models.correction_decision import CorrectionDecision
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
)
from app.models.upload import SourceRecord, UploadBatch
from app.modules.corrections.decisions import decision_info
from app.modules.corrections.export_data import (
    coordinate_sources,
    result_columns,
    source_label,
    target_columns,
    text,
)
from app.modules.corrections.service import CorrectionKind, check_process
from app.modules.corrections.spreadsheet import (
    RESULT_HEADERS,
    RESULT_WIDTHS,
    Spreadsheet,
)
from app.modules.upload.normalization import extract_standard_fields

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
ResultFilter = Literal["selected", "all", "not_selected", "cancelled", "not_processed"]


def result_scope(
    db: Session, kind: CorrectionKind, process_id: int, generation: int | None = None
) -> tuple[CorrectionCheck, ReconciliationProcess, MatchingRun]:
    check, process = check_process(db, kind, process_id)
    runs = db.query(MatchingRun).filter_by(process_id=process_id)
    if generation is not None:
        runs = runs.filter_by(generation=generation)
    run = runs.order_by(MatchingRun.generation.desc()).first()
    if run is None:
        raise HTTPException(404, "Versi pemeriksaan tidak ditemukan")
    return check, process, run


def latest_decisions(db: Session, process_id: int, generation: int) -> Subquery:
    revisions = (
        db.query(
            CorrectionDecision.target_record_id.label("record_id"),
            func.max(CorrectionDecision.revision).label("revision"),
        )
        .filter(
            CorrectionDecision.process_id == process_id,
            CorrectionDecision.generation <= generation,
        )
        .group_by(CorrectionDecision.target_record_id)
        .subquery()
    )
    return (
        db.query(
            CorrectionDecision.id,
            CorrectionDecision.target_record_id,
            CorrectionDecision.candidate_id,
        )
        .join(
            revisions,
            and_(
                CorrectionDecision.target_record_id == revisions.c.record_id,
                CorrectionDecision.revision == revisions.c.revision,
            ),
        )
        .filter(CorrectionDecision.process_id == process_id)
        .subquery()
    )


def results_summary(
    db: Session, kind: CorrectionKind, process_id: int, generation: int | None = None
) -> dict[str, Any]:
    check, process, run = result_scope(db, kind, process_id, generation)
    batch = db.get(UploadBatch, process.target_batch_id)
    assert batch is not None
    latest = latest_decisions(db, process_id, run.generation)
    chosen = (
        db.query(func.count())
        .select_from(latest)
        .filter(latest.c.candidate_id.is_not(None))
        .scalar()
        or 0
    )
    cancelled = (
        db.query(func.count())
        .select_from(latest)
        .filter(latest.c.candidate_id.is_(None))
        .scalar()
        or 0
    )
    outcomes = {
        status: number
        for status, number in db.query(
            CorrectionTarget.search_status, func.count(CorrectionTarget.id)
        )
        .filter_by(run_id=run.id)
        .group_by(CorrectionTarget.search_status)
        .all()
    }
    saved = sum(outcomes.values())
    matched = outcomes.get("matched", 0)
    total = batch.total_rows or 0
    events = (
        db.query(CorrectionDecision.id)
        .filter(
            CorrectionDecision.process_id == process_id,
            CorrectionDecision.generation <= run.generation,
        )
        .count()
    )
    return {
        "process_id": process.id,
        "process_name": process.process_name,
        "category": kind.value,
        "batch_id": batch.id,
        "filename": batch.filename,
        "pdpj_review_id": check.pdpj_review_id,
        "generation": run.generation,
        "radius_meters": run.radius_meters,
        "matching_status": run.status.value,
        "review_status": process.review_status.value,
        "processing_state": (run.processing or {}).get("state", run.status.value),
        "partial": run.status != ProcessStatus.COMPLETED,
        "total_targets": total,
        "saved_rows": saved,
        "not_processed": max(0, total - saved),
        "matched_targets": matched,
        "unmatched_targets": saved - matched,
        "chosen_count": chosen,
        "cancelled_count": cancelled,
        "not_selected": max(0, total - chosen),
        "decision_events": events,
        "total_candidates": db.query(MatchCandidate.id)
        .filter_by(process_id=process_id, generation=run.generation)
        .count(),
        "valid_count": chosen,
        "rejected_count": 0,
        "pending_count": max(0, total - chosen),
        "is_empty": False,
    }


def result_query(
    db: Session,
    process: ReconciliationProcess,
    run: MatchingRun,
    q: str,
    status: ResultFilter,
) -> OrmQuery[Any]:
    latest = latest_decisions(db, process.id, run.generation)
    query = (
        db.query(SourceRecord, CorrectionTarget, CorrectionDecision)
        .outerjoin(
            CorrectionTarget,
            and_(
                CorrectionTarget.source_record_id == SourceRecord.id,
                CorrectionTarget.run_id == run.id,
            ),
        )
        .outerjoin(latest, latest.c.target_record_id == SourceRecord.id)
        .outerjoin(CorrectionDecision, CorrectionDecision.id == latest.c.id)
        .filter(SourceRecord.batch_id == process.target_batch_id)
        .options(
            load_only(
                SourceRecord.id, SourceRecord.row_number, SourceRecord.normalized_data
            )
        )
    )
    if status == "selected":
        query = query.filter(CorrectionDecision.candidate_id.is_not(None))
    elif status == "not_selected":
        query = query.filter(CorrectionDecision.candidate_id.is_(None))
    elif status == "cancelled":
        query = query.filter(
            CorrectionDecision.id.is_not(None),
            CorrectionDecision.candidate_id.is_(None),
        )
    elif status == "not_processed":
        query = query.filter(CorrectionTarget.id.is_(None))
    if q.strip():
        pattern = (
            "%"
            + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        query = query.filter(
            or_(
                *(
                    func.coalesce(
                        CorrectionTarget.fields[key].as_string(),
                        SourceRecord.normalized_data[key].as_string(),
                    ).ilike(pattern, escape="\\")
                    for key in ("idpel", "nama", "meter_ref", "target_ref")
                ),
                *(
                    CorrectionDecision.candidate["fields"][key]
                    .as_string()
                    .ilike(pattern, escape="\\")
                    for key in ("idpel", "nama")
                ),
                CorrectionDecision.actor.ilike(pattern, escape="\\"),
            )
        )
    return query


def result_info(
    source: SourceRecord,
    outcome: CorrectionTarget | None,
    decision: CorrectionDecision | None,
    batch: UploadBatch,
) -> dict[str, Any]:
    target = (
        decision.target_fields
        if decision
        else outcome.fields
        if outcome
        else source.normalized_data
    )
    if target is None:
        target = extract_standard_fields(source.data or {}, batch.column_mapping)
    status = (
        "selected"
        if decision and decision.candidate_id is not None
        else "cancelled"
        if decision
        else "not_selected"
        if outcome
        else "not_processed"
    )
    return {
        "record_id": source.id,
        "row_number": source.row_number,
        "status": status,
        "search_status": outcome.search_status if outcome else "not_checked",
        "target_fields": target,
        "choice": decision_info(decision) if decision else None,
    }


@router.get("/{kind}/checks/{process_id}/results")
def saved_results(
    kind: CorrectionKind,
    process_id: int,
    db: DbSession,
    generation: int | None = Query(None, ge=1),
    q: str = Query("", max_length=120),
    status: ResultFilter = "selected",
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    _, process, run = result_scope(db, kind, process_id, generation)
    query = result_query(db, process, run, q, status)
    total = query.count()
    batch = db.get(UploadBatch, process.target_batch_id)
    assert batch is not None
    rows = query.order_by(SourceRecord.id).offset(skip).limit(limit).all()
    return {
        "summary": results_summary(db, kind, process_id, run.generation),
        "total": total,
        "items": [
            result_info(source, outcome, event, batch)
            for source, outcome, event in rows
        ],
    }


@router.get("/{kind}/checks/{process_id}/results/history")
def result_history(
    kind: CorrectionKind,
    process_id: int,
    db: DbSession,
    record_id: int | None = Query(None, gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    check_process(db, kind, process_id)
    query = (
        db.query(CorrectionDecision, SourceRecord.row_number)
        .join(SourceRecord, SourceRecord.id == CorrectionDecision.target_record_id)
        .filter(CorrectionDecision.process_id == process_id)
    )
    if record_id is not None:
        query = query.filter(CorrectionDecision.target_record_id == record_id)
    total = query.count()
    return {
        "total": total,
        "items": [
            {
                **decision_info(event),
                "record_id": event.target_record_id,
                "row_number": row_number,
            }
            for event, row_number in query.order_by(
                CorrectionDecision.created_at.desc(), CorrectionDecision.id.desc()
            )
            .offset(skip)
            .limit(limit)
        ],
    }


def export_info(
    book: Spreadsheet, batch: UploadBatch, process_id: int, generation: int, scope: str
) -> None:
    sheet = book.sheet("Informasi", ["Keterangan", "Nilai"], [36, 100])
    entries: list[list[Any]] = [
        ["Proses", process_id],
        ["Berkas target", source_label(batch.filename, batch.source_sheet)],
        ["Versi pemeriksaan", generation],
        ["Cakupan ekspor", scope],
        [
            "noagenda / verif",
            "Nilai dari data target; kosong jika sumber tidak mengisinya.",
        ],
        [
            "idpelanggan",
            "IDPEL kandidat yang dipilih; kosong jika belum dipilih atau dibatalkan.",
        ],
        [
            "jenispelanggan",
            "Jenis pelanggan kandidat; memakai target jika kandidat tidak mengisinya.",
        ],
        [
            "latitudey / longitudex",
            "Koordinat target awal, terpisah dari koordinat kandidat.",
        ],
        [
            "sumber file (sheet) / sel",
            "Observasi master berkoordinat sama dengan kandidat pilihan. Beberapa sumber dipisahkan baris baru.",
        ],
        [
            "x_acc / y_acc",
            "Koordinat kandidat yang disetujui: x_acc adalah longitude (bujur), y_acc adalah latitude (lintang).",
        ],
        [
            "Data Target",
            "Identitas, koordinat, berkas, dan baris target sebelum koreksi.",
        ],
        [
            "Observasi Sumber",
            "Seluruh bukti kandidat. koordinat_dipakai menandai sumber koordinat pilihan.",
        ],
        [
            "Tipe data",
            "IDPEL, nomor agenda, dan koordinat memakai teks untuk menjaga nol di depan dan digit desimal.",
        ],
        [
            "Riwayat",
            "Pemilihan, penggantian, dan pembatalan tetap tersimpan. Waktu menggunakan UTC.",
        ],
    ]
    for values in entries:
        book.append(sheet, values)


def evidence_sheet(book: Spreadsheet) -> Any:
    return book.sheet(
        "Observasi Sumber",
        [
            "baris_target",
            "revisi_pilihan",
            "idpelanggan",
            "jenispelanggan",
            "latitudey",
            "longitudex",
            "sumber file (sheet)",
            "sel (baris ke berapa)",
            "koordinat_dipakai",
        ],
        [18, 18, 22, 22, 24, 24, 58, 26, 22],
    )


def append_evidence(
    book: Spreadsheet,
    sheet: Any,
    source: SourceRecord,
    decision: CorrectionDecision | None,
) -> None:
    if decision is None or decision.candidate_id is None:
        return
    candidate = decision.candidate
    selected_sources = coordinate_sources(candidate)
    for observation in candidate.get("observations", []):
        fields = observation.get("fields", {})
        book.append(
            sheet,
            [
                source.row_number,
                decision.revision,
                text(fields.get("idpel")),
                fields.get("jenis_pel"),
                text(fields.get("lat")),
                text(fields.get("lon")),
                source_label(
                    observation.get("filename"), observation.get("source_sheet")
                ),
                observation.get("row_number"),
                "Ya" if observation in selected_sources else "Tidak",
            ],
        )


def export_results(
    db: Session,
    kind: CorrectionKind,
    process_id: int,
    generation: int | None = None,
    q: str = "",
    status: ResultFilter = "selected",
) -> StreamingResponse:
    _, process, run = result_scope(db, kind, process_id, generation)
    batch = db.get(UploadBatch, process.target_batch_id)
    assert batch is not None
    book = Spreadsheet()
    main = book.sheet("Hasil Koreksi", RESULT_HEADERS, RESULT_WIDTHS)
    targets = book.sheet("Data Target", RESULT_HEADERS[:8], RESULT_WIDTHS[:8])
    evidence = evidence_sheet(book)
    audit = book.sheet(
        "Keputusan Aktif",
        [
            "baris_target",
            "status",
            "versi_pilihan",
            "revisi_pilihan",
            "petugas",
            "waktu_utc",
            "alasan",
            "jarak_meter",
        ],
        [18, 24, 18, 18, 28, 30, 60, 18],
    )
    for source, outcome, decision in (
        result_query(db, process, run, q, status)
        .options(undefer(SourceRecord.data))
        .order_by(SourceRecord.id)
        .yield_per(200)
    ):
        item = result_info(source, outcome, decision, batch)
        candidate = (
            decision.candidate if decision and decision.candidate_id is not None else {}
        )
        book.append(
            main, result_columns(source, batch, item["target_fields"], candidate)
        )
        book.append(targets, target_columns(source, batch, item["target_fields"]))
        append_evidence(book, evidence, source, decision)
        book.append(
            audit,
            [
                source.row_number,
                item["status"],
                decision.generation if decision else None,
                decision.revision if decision else None,
                decision.actor if decision else None,
                decision.created_at.isoformat() if decision else None,
                decision.reason if decision else None,
                candidate.get("distance_meters"),
            ],
        )
    export_info(
        book,
        batch,
        process_id,
        run.generation,
        f"Filter: {status}; pencarian: {q or '(semua)'}",
    )
    return book.response(f"hasil_koreksi_{kind.value}_{process_id}.xlsx")


@router.get("/{kind}/checks/{process_id}/results/history/export")
def download_history(
    kind: CorrectionKind,
    process_id: int,
    db: DbSession,
    record_id: int | None = Query(None, gt=0),
) -> StreamingResponse:
    _, process, run = result_scope(db, kind, process_id)
    batch = db.get(UploadBatch, process.target_batch_id)
    assert batch is not None
    query = (
        db.query(CorrectionDecision, SourceRecord)
        .join(SourceRecord, SourceRecord.id == CorrectionDecision.target_record_id)
        .filter(CorrectionDecision.process_id == process_id)
        .options(load_only(SourceRecord.id, SourceRecord.row_number, SourceRecord.data))
    )
    if record_id is not None:
        query = query.filter(CorrectionDecision.target_record_id == record_id)
    book = Spreadsheet()
    main = book.sheet(
        "Riwayat Pilihan",
        [
            *RESULT_HEADERS,
            "baris_target",
            "idpelanggan_awal",
            "status",
            "versi_pilihan",
            "revisi_pilihan",
            "petugas",
            "waktu_utc",
            "alasan",
        ],
        [*RESULT_WIDTHS, 18, 22, 24, 18, 18, 28, 30, 60],
    )
    evidence = evidence_sheet(book)
    for decision, source in query.order_by(
        CorrectionDecision.created_at.desc(), CorrectionDecision.id.desc()
    ).yield_per(200):
        candidate = decision.candidate if decision.candidate_id is not None else {}
        book.append(
            main,
            [
                *result_columns(source, batch, decision.target_fields, candidate),
                source.row_number,
                text(decision.target_fields.get("idpel")),
                "Kandidat dipilih"
                if decision.candidate_id is not None
                else "Pilihan dibatalkan",
                decision.generation,
                decision.revision,
                decision.actor,
                decision.created_at.isoformat(),
                decision.reason,
            ],
        )
        append_evidence(book, evidence, source, decision)
    export_info(
        book,
        batch,
        process_id,
        run.generation,
        "Seluruh riwayat pada target terpilih"
        if record_id is not None
        else "Seluruh riwayat proses",
    )
    return book.response(f"riwayat_koreksi_{kind.value}_{process_id}.xlsx")


@router.get("/{kind}/checks/{process_id}/results/export")
def download_results(
    kind: CorrectionKind,
    process_id: int,
    db: DbSession,
    generation: int | None = Query(None, ge=1),
    q: str = Query("", max_length=120),
    status: ResultFilter = "selected",
) -> StreamingResponse:
    return export_results(db, kind, process_id, generation, q, status)
