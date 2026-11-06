"""Preview and atomically audit distance-first, one-to-one candidate selection."""

import hashlib
import json
from collections import Counter
from itertools import groupby
from typing import Annotated, Any, Literal

from app.database import get_db
from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.correction_decision import CorrectionDecision
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from app.models.upload import SourceRecord, UploadBatch
from app.modules.auth.security import CurrentActor
from app.modules.corrections.automatic_candidates import candidate_frontier
from app.modules.corrections.export_data import result_columns
from app.modules.corrections.selection_state import current_choices, identity_owners
from app.modules.corrections.service import CorrectionKind, check_process, selected_run
from app.modules.corrections.spreadsheet import (
    CANDIDATE_DISTANCE_HEADER,
    DISTANCE_NUMBER_FORMAT,
    RESULT_HEADERS,
    RESULT_WIDTHS,
    Spreadsheet,
)
from app.modules.corrections.tie_suggestions import propose_ties
from app.modules.pdpj.service import lock_review_session
from app.modules.upload.storage import database_write_error
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    generation: int = Field(ge=1)
    radius_meters: float = Field(gt=0, le=100000)
    tie_strategy: Literal["review", "suggest"] = "review"


class ApplyRequest(PreviewRequest):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class SuggestionExportRequest(PreviewRequest):
    tie_strategy: Literal["suggest"] = "suggest"
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def writable_run(
    db: Session, kind: CorrectionKind, process_id: int, req: PreviewRequest
) -> tuple[ReconciliationProcess, MatchingRun]:
    _, process = check_process(db, kind, process_id)
    latest = (
        db.query(MatchingRun)
        .filter_by(process_id=process_id)
        .order_by(MatchingRun.generation.desc())
        .first()
    )
    if (
        latest is None
        or latest.generation != req.generation
        or latest.status != ProcessStatus.COMPLETED
        or process.current_generation != req.generation
        or process.review_status == ReviewStatus.FINALIZED
    ):
        raise HTTPException(
            409,
            "Pilihan otomatis memerlukan hasil terbaru yang selesai dan belum final",
        )
    run = selected_run(db, process, req.generation)
    assert run is not None
    if req.radius_meters > run.radius_meters:
        raise HTTPException(
            422, "Radius pilihan otomatis melebihi radius pemeriksaan tersimpan"
        )
    return process, run


def decision_version(db: Session, process_id: int) -> int:
    return (
        db.query(func.max(CorrectionDecision.id))
        .filter_by(process_id=process_id)
        .scalar()
        or 0
    )


def build_plan(
    db: Session, kind: CorrectionKind, process_id: int, req: PreviewRequest
) -> dict[str, Any]:
    _, run = writable_run(db, kind, process_id, req)
    if req.tie_strategy == "suggest":
        base = build_plan(
            db, kind, process_id, req.model_copy(update={"tie_strategy": "review"})
        )
        plan = propose_ties(db, run, req.radius_meters, base)
        plan["fingerprint"] = hashlib.sha256(
            json.dumps(
                [
                    base["fingerprint"],
                    "suggest",
                    sorted(plan["_suggestions"].items()),
                    plan["unpaired"],
                ],
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return plan
    version = decision_version(db, process_id)
    # Include cancellations: an explicit operator decision is never silently undone.
    protected = {
        record
        for (record,) in current_choices(db, process_id).with_entities(
            CorrectionDecision.target_record_id
        )
    }
    owners = identity_owners(db, process_id)
    if any(len(targets) > 1 for targets in owners.values()):
        raise HTTPException(
            409,
            "Pilihan tersimpan masih memakai IDPEL yang sama pada beberapa target. Perbaiki melalui Peta Koreksi terlebih dahulu.",
        )
    used = set(owners)
    outcomes = {
        record: (status, row)
        for record, status, row in db.query(
            CorrectionTarget.source_record_id,
            CorrectionTarget.search_status,
            SourceRecord.row_number,
        )
        .join(SourceRecord, SourceRecord.id == CorrectionTarget.source_record_id)
        .filter(CorrectionTarget.run_id == run.id)
    }
    selected: dict[int, int] = {}
    tied: set[int] = set()
    has_candidate: set[int] = set()
    fallback = 0
    pairs = candidate_frontier(db, run, req.radius_meters, protected, selected, tied)
    for _, equal_distance in groupby(pairs, key=lambda pair: pair.distance_meters):
        # Summarize equal-distance edges with bounded state per target/identity.
        first: dict[int, Any] = {}
        target_counts: Counter[int] = Counter()
        id_counts: Counter[str] = Counter()
        identities: set[str] = set()
        for pair in equal_distance:
            record, identity = pair.target_record_id, pair.candidate_idpel
            if record in protected or not identity:
                continue
            has_candidate.add(record)
            if record in selected or record in tied or identity in used:
                continue
            first.setdefault(record, pair)
            target_counts[record] += 1
            id_counts[identity] += 1
            identities.add(identity)
        # Exact ties affecting either side require human review, never row priority.
        for record, pair in first.items():
            if target_counts[record] > 1 or id_counts[pair.candidate_idpel] > 1:
                tied.add(record)
            else:
                selected[record] = pair.id
                fallback += int(pair.rank > 1)
        used.update(identities)

    review = []
    for record, (status, row) in outcomes.items():
        if record in protected or record in selected:
            continue
        reason = (
            "equal_distance"
            if record in tied
            else "candidates_used"
            if record in has_candidate
            else "outside_radius"
            if status == "matched"
            else status
        )
        review.append({"record_id": record, "row_number": row, "reason": reason})
    review.sort(key=lambda item: (item["row_number"], item["record_id"]))
    digest = hashlib.sha256(
        json.dumps(
            [
                process_id,
                run.id,
                req.radius_meters,
                version,
                sorted(selected.items()),
                review,
            ],
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "tie_strategy": "review",
        "generation": run.generation,
        "radius_meters": req.radius_meters,
        "total_targets": len(outcomes),
        "protected_count": len(protected),
        "selected_count": len(selected),
        "fallback_count": fallback,
        "review_count": len(review),
        "review_reasons": dict(Counter(item["reason"] for item in review)),
        "review": review,
        "fingerprint": digest,
        "_selected": selected,
        "_version": version,
    }


def public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if not key.startswith("_")}


@router.post("/{kind}/checks/{process_id}/automatic/preview")
def preview_selection(
    kind: CorrectionKind, process_id: int, req: PreviewRequest, db: DbSession
) -> dict[str, Any]:
    return public_plan(build_plan(db, kind, process_id, req))


@router.post("/{kind}/checks/{process_id}/automatic/suggestions/export")
def export_suggestions(
    kind: CorrectionKind, process_id: int, req: SuggestionExportRequest, db: DbSession
):
    plan = build_plan(db, kind, process_id, req)
    if plan["fingerprint"] != req.fingerprint:
        raise HTTPException(
            409,
            "Usulan atau pilihan tersimpan berubah. Muat ulang pratinjau sebelum mengunduh.",
        )
    process, run = writable_run(db, kind, process_id, req)
    batch = db.get(UploadBatch, process.target_batch_id)
    assert batch is not None
    book = Spreadsheet()
    sheet = book.sheet(
        "Usulan Jarak Sama",
        [*RESULT_HEADERS, "Status Usulan", "Baris Target"],
        [*RESULT_WIDTHS, 28, 18],
        number_formats={CANDIDATE_DISTANCE_HEADER: DISTANCE_NUMBER_FORMAT},
    )
    candidates = [item["candidate_id"] for item in plan["suggestions"]]
    for offset in range(0, len(candidates), 200):
        rows = (
            db.query(
                MatchCandidate,
                CorrectionCandidateEvidence,
                CorrectionTarget,
                SourceRecord,
            )
            .join(
                CorrectionCandidateEvidence,
                CorrectionCandidateEvidence.candidate_id == MatchCandidate.id,
            )
            .join(
                CorrectionTarget,
                (CorrectionTarget.run_id == run.id)
                & (
                    CorrectionTarget.source_record_id == MatchCandidate.target_record_id
                ),
            )
            .join(SourceRecord, SourceRecord.id == MatchCandidate.target_record_id)
            .filter(MatchCandidate.id.in_(candidates[offset : offset + 200]))
            .order_by(SourceRecord.id)
            .all()
        )
        if len(rows) != len(candidates[offset : offset + 200]):
            raise HTTPException(
                409, "Bukti usulan belum lengkap. Unduhan belum dapat dibuat."
            )
        for candidate, evidence, target, source in rows:
            snapshot = {
                "fields": evidence.fields,
                "observations": evidence.observations,
                "distance_meters": candidate.distance_meters,
            }
            book.append(
                sheet,
                [
                    *result_columns(
                        source,
                        batch,
                        target.fields,
                        snapshot,
                        radius_meters=req.radius_meters,
                    ),
                    "Perlu verifikasi",
                    source.row_number,
                ],
            )
    radius = f"{req.radius_meters:g}".replace(".", "_")
    return book.response(
        f"usulan_jarak_sama_{kind.value}_{process_id}_radius_{radius}m_v{run.generation}.xlsx"
    )


def operation_prefix(request_key: str) -> str:
    return "auto_" + hashlib.sha256(request_key.encode()).hexdigest()[:32] + "_"


def replay(
    db: Session, process_id: int, req: ApplyRequest, actor: str
) -> dict[str, Any] | None:
    events = (
        db.query(
            CorrectionDecision.process_id,
            CorrectionDecision.generation,
            CorrectionDecision.actor,
            CorrectionDecision.reason,
        )
        .filter(
            CorrectionDecision.request_key.startswith(
                operation_prefix(req.request_key), autoescape=True
            )
        )
        .all()
    )
    if not events:
        return None
    reason = automatic_reason(req)
    if any(
        event.process_id != process_id
        or event.generation != req.generation
        or event.actor != actor
        or event.reason != reason
        for event in events
    ):
        raise HTTPException(
            409, "Kunci permintaan sudah dipakai untuk pilihan otomatis berbeda"
        )
    return {"selected_count": len(events), "already_applied": True}


def automatic_reason(req: ApplyRequest) -> str:
    mode = (
        " mode usulan jarak sama; hanya pilihan tanpa ambiguitas disimpan;"
        if req.tie_strategy == "suggest"
        else ""
    )
    return f"Pilihan otomatis jarak terdekat;{mode} satu IDPEL satu target; radius {req.radius_meters:g} m; pratinjau {req.fingerprint}"


@router.post("/{kind}/checks/{process_id}/automatic/apply")
def apply_selection(
    kind: CorrectionKind,
    process_id: int,
    req: ApplyRequest,
    db: DbSession,
    actor: CurrentActor,
) -> dict[str, Any]:
    check_process(db, kind, process_id)
    previous = replay(db, process_id, req, actor)
    if previous:
        return previous
    plan = build_plan(db, kind, process_id, req)
    if plan["fingerprint"] != req.fingerprint:
        raise HTTPException(
            409,
            "Pilihan atau versi pemeriksaan berubah. Buat pratinjau ulang sebelum menyimpan.",
        )
    # Expensive planning is read-only. Acquire the writer lock only for validation/save.
    db.rollback()
    try:
        lock_review_session(db)
        db.query(ReconciliationProcess).filter_by(
            id=process_id
        ).populate_existing().with_for_update().one()
        previous = replay(db, process_id, req, actor)
        if previous:
            return previous
        process, run = writable_run(db, kind, process_id, req)
        if decision_version(db, process_id) != plan["_version"]:
            raise HTTPException(
                409,
                "Pilihan berubah saat menyiapkan penyimpanan. Buat pratinjau ulang.",
            )
        selections = list(plan["_selected"].values())
        for offset in range(0, len(selections), 200):
            ids = selections[offset : offset + 200]
            rows = (
                db.query(MatchCandidate, CorrectionCandidateEvidence, CorrectionTarget)
                .join(
                    CorrectionCandidateEvidence,
                    CorrectionCandidateEvidence.candidate_id == MatchCandidate.id,
                )
                .join(
                    CorrectionTarget,
                    (CorrectionTarget.run_id == run.id)
                    & (
                        CorrectionTarget.source_record_id
                        == MatchCandidate.target_record_id
                    ),
                )
                .filter(MatchCandidate.id.in_(ids))
                .all()
            )
            if len(rows) != len(ids):
                raise HTTPException(
                    409,
                    "Bukti kandidat belum lengkap. Pilihan otomatis belum disimpan.",
                )
            events = []
            for candidate, evidence, target in rows:
                if evidence.fields.get("idpel") != candidate.candidate_idpel:
                    raise HTTPException(
                        409, "Identitas kandidat tidak sesuai dengan bukti tersimpan"
                    )
                events.append(
                    {
                        "process_id": process_id,
                        "target_record_id": candidate.target_record_id,
                        "generation": run.generation,
                        "revision": 1,
                        "candidate_id": candidate.id,
                        "request_key": operation_prefix(req.request_key)
                        + str(candidate.target_record_id),
                        "actor": actor,
                        "reason": automatic_reason(req),
                        "target_fields": target.fields,
                        "candidate": {
                            "id": candidate.id,
                            "rank": candidate.rank,
                            "distance_meters": candidate.distance_meters,
                            "fields": evidence.fields,
                            "observations": evidence.observations,
                        },
                    }
                )
            db.bulk_insert_mappings(CorrectionDecision.__mapper__, events)
            db.query(MatchCandidate).filter(MatchCandidate.id.in_(ids)).update(
                {"is_accepted": 1}, synchronize_session=False
            )
        if selections:
            process.review_status = ReviewStatus.IN_PROGRESS
        db.commit()
    except SQLAlchemyError as exc:
        raise database_write_error(db, exc, "penyimpanan pilihan otomatis") from exc
    except Exception:
        db.rollback()
        raise
    return {**public_plan(plan), "already_applied": False}
