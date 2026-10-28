"""Serialize one active choice per target and retain every change as evidence."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.correction_decision import CorrectionDecision
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ReconciliationProcess,
    ReviewStatus,
)
from app.modules.corrections.service import CorrectionKind, check_process, selected_run
from app.modules.pdpj.service import lock_review_session

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


class ChoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generation: int = Field(ge=1)
    expected_revision: int = Field(ge=0)
    candidate_id: int | None = Field(default=None, gt=0)
    actor: str = Field(min_length=1, max_length=80)
    reason: str = Field(default="", max_length=1000)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("actor", "reason")
    @classmethod
    def trim_text(cls, value: str, info: Any) -> str:
        text = value.strip()
        if info.field_name == "actor" and not text:
            raise ValueError("Nama petugas wajib diisi")
        return text


def decision_info(event: CorrectionDecision) -> dict[str, Any]:
    return {
        "id": event.id,
        "revision": event.revision,
        "generation": event.generation,
        "candidate_id": event.candidate_id,
        "candidate": event.candidate,
        "target_fields": event.target_fields,
        "actor": event.actor,
        "reason": event.reason,
        "created_at": event.created_at,
    }


def choice_history(db: Session, process_id: int, record_id: int) -> dict[str, Any]:
    events = (
        db.query(CorrectionDecision)
        .filter(
            CorrectionDecision.process_id == process_id,
            CorrectionDecision.target_record_id == record_id,
        )
        .order_by(CorrectionDecision.revision.desc())
        .all()
    )
    return {
        "revision": events[0].revision if events else 0,
        "current": decision_info(events[0]) if events else None,
        "history": [decision_info(event) for event in events],
    }


def target_scope(
    db: Session, kind: CorrectionKind, process_id: int, record_id: int
) -> ReconciliationProcess:
    _, process = check_process(db, kind, process_id)
    if (
        not db.query(CorrectionTarget)
        .join(MatchingRun)
        .filter(
            MatchingRun.process_id == process_id,
            CorrectionTarget.source_record_id == record_id,
        )
        .first()
    ):
        raise HTTPException(404, "Baris pada pemeriksaan ini tidak ditemukan")
    return process


@router.get("/{kind}/checks/{process_id}/records/{record_id}/choice")
def get_choice(
    kind: CorrectionKind, process_id: int, record_id: int, db: DbSession
) -> dict[str, Any]:
    target_scope(db, kind, process_id, record_id)
    return choice_history(db, process_id, record_id)


@router.post("/{kind}/checks/{process_id}/records/{record_id}/choice")
def choose_candidate(
    kind: CorrectionKind,
    process_id: int,
    record_id: int,
    req: ChoiceRequest,
    db: DbSession,
) -> dict[str, Any]:
    lock_review_session(db)
    process = target_scope(db, kind, process_id, record_id)
    process = (
        db.query(ReconciliationProcess)
        .filter(ReconciliationProcess.id == process_id)
        .populate_existing()
        .with_for_update()
        .one()
    )
    existing = (
        db.query(CorrectionDecision).filter_by(request_key=req.request_key).first()
    )
    if existing:
        if (
            existing.process_id != process_id
            or existing.target_record_id != record_id
            or existing.candidate_id != req.candidate_id
            or existing.generation != req.generation
            or existing.actor != req.actor
            or existing.reason != req.reason
            or existing.revision != req.expected_revision + 1
        ):
            raise HTTPException(
                409, "Kunci permintaan sudah dipakai untuk pilihan berbeda"
            )
        return choice_history(db, process_id, record_id)
    latest = (
        db.query(MatchingRun)
        .filter_by(process_id=process_id)
        .order_by(MatchingRun.generation.desc())
        .first()
    )
    incremental = bool(latest and latest.processing)
    writable_generation = (
        latest.generation if incremental and latest else process.current_generation
    )
    if (
        req.generation != writable_generation
        or process.review_status == ReviewStatus.FINALIZED
    ):
        raise HTTPException(
            409, "Pilihan hanya dapat diubah pada hasil terbaru yang belum final"
        )
    if not incremental and (
        db.query(MatchingRun)
        .filter(
            MatchingRun.process_id == process_id,
            MatchingRun.status.in_(["queued", "running"]),
        )
        .first()
    ):
        raise HTTPException(409, "Tunggu pencarian selesai sebelum memilih kandidat")
    run = selected_run(db, process, req.generation, include_partial=incremental)
    assert run is not None
    target = (
        db.query(CorrectionTarget)
        .filter_by(run_id=run.id, source_record_id=record_id)
        .one_or_none()
    )
    if target is None:
        raise HTTPException(409, "Baris ini belum selesai diperiksa dan disimpan")
    history = choice_history(db, process_id, record_id)
    if history["revision"] != req.expected_revision:
        raise HTTPException(
            409, "Pilihan telah berubah. Muat ulang detail sebelum menyimpan."
        )
    if history["current"] and not req.reason:
        raise HTTPException(
            422, "Alasan wajib diisi untuk mengganti atau membatalkan pilihan"
        )
    snapshot: dict[str, Any] = {}
    if req.candidate_id is not None:
        result = (
            db.query(MatchCandidate, CorrectionCandidateEvidence)
            .join(
                CorrectionCandidateEvidence,
                CorrectionCandidateEvidence.candidate_id == MatchCandidate.id,
            )
            .filter(
                MatchCandidate.id == req.candidate_id,
                MatchCandidate.process_id == process_id,
                MatchCandidate.generation == req.generation,
                MatchCandidate.target_record_id == record_id,
            )
            .first()
        )
        if result is None:
            raise HTTPException(
                404, "Kandidat pada baris dan versi ini tidak ditemukan"
            )
        if target.search_status != "matched":
            raise HTTPException(
                409, "Baris ini belum memenuhi syarat pemilihan kandidat"
            )
        candidate, evidence = result
        snapshot = {
            "id": candidate.id,
            "rank": candidate.rank,
            "distance_meters": candidate.distance_meters,
            "fields": evidence.fields,
            "observations": evidence.observations,
        }
    elif not history["current"] or history["current"]["candidate_id"] is None:
        raise HTTPException(422, "Belum ada pilihan yang dapat dibatalkan")
    db.query(MatchCandidate).filter_by(
        process_id=process_id, target_record_id=record_id
    ).update({"is_accepted": 0})
    if req.candidate_id is not None:
        db.query(MatchCandidate).filter_by(id=req.candidate_id).update(
            {"is_accepted": 1}
        )
    db.add(
        CorrectionDecision(
            process_id=process_id,
            target_record_id=record_id,
            generation=req.generation,
            revision=req.expected_revision + 1,
            candidate_id=req.candidate_id,
            request_key=req.request_key,
            actor=req.actor,
            reason=req.reason,
            target_fields=target.fields,
            candidate=snapshot,
        )
    )
    process.review_status = ReviewStatus.IN_PROGRESS
    db.commit()
    return choice_history(db, process_id, record_id)
