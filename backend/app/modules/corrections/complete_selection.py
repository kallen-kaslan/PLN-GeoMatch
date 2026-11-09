"""Preview and save distance-first automatic pairs, including targeted radius extensions."""

import hashlib
import json
from collections import Counter
from time import monotonic
from typing import Any, Literal

from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget, utc_now
from app.models.correction_decision import CorrectionDecision
from app.models.master_sisa import MasterSisaRecord
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from app.models.upload import SourceRecord
from app.modules.auth.security import CurrentActor
from app.modules.corrections.advanced_search import pinned_sources
from app.modules.corrections.automatic import (
    DbSession,
    PreviewRequest,
    build_plan,
    decision_version,
    public_plan,
    writable_run,
)
from app.modules.corrections.candidate_scope import (
    candidate_generations,
    candidate_scope,
)
from app.modules.corrections.selection_state import identity_owners
from app.modules.corrections.service import CorrectionKind, check_process
from app.modules.corrections.unpaired_search import UnpairedRequest, find_unpaired
from app.modules.pdpj.service import lock_review_session
from app.modules.upload.storage import database_write_error
from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import func, insert, literal, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter()


class CompleteRequest(PreviewRequest):
    tie_strategy: Literal["suggest"] = "suggest"
    max_radius_meters: float = Field(500, gt=0, le=5000)


class CompleteApply(CompleteRequest):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


def complete_plan(
    db: Session, kind: CorrectionKind, process_id: int, req: CompleteRequest
) -> dict[str, Any]:
    if req.max_radius_meters < req.radius_meters:
        raise HTTPException(
            422, "Batas radius harus sama atau lebih besar dari radius awal"
        )
    process, run = writable_run(db, kind, process_id, req)
    pinned_sources(db, process)
    base = build_plan(db, kind, process_id, req)
    selected = {**base["_selected"], **base["_suggestions"]}
    methods = {record: "nearest" for record in base["_selected"]}
    methods.update({record: "equal_distance" for record in base["_suggestions"]})
    additions: dict[int, Any] = {}
    remaining = base["unpaired"]
    expanded_records: list[int] = []
    result_radius = req.radius_meters
    if remaining and req.max_radius_meters > req.radius_meters:
        expanded_records = [item["record_id"] for item in remaining]
        found = find_unpaired(
            db,
            process,
            run,
            UnpairedRequest(
                generation=req.generation,
                radius_meters=req.radius_meters,
                fingerprint=base["fingerprint"],
                search_radius_meters=req.max_radius_meters,
            ),
            base,
        )
        remaining = []
        result_radius = req.max_radius_meters
        for item in found["items"]:
            candidate = item["candidate"]
            record = item["record_id"]
            if candidate is None:
                remaining.append(
                    {key: item[key] for key in ("record_id", "row_number", "reason")}
                )
                continue
            stored = (
                db.query(MatchCandidate)
                .filter(
                    candidate_scope(run),
                    MatchCandidate.target_record_id == record,
                    MatchCandidate.candidate_idpel == candidate["idpel"],
                )
                .first()
            )
            if stored:
                if abs(stored.distance_meters - candidate["distance_meters"]) > 1e-6:
                    raise HTTPException(
                        409, "Bukti jarak kandidat berubah. Buat pemeriksaan ulang."
                    )
                selected[record] = stored.id
            else:
                additions[record] = candidate
            methods[record] = "expanded_radius"
    selections = []
    ids = list(selected.values())
    for offset in range(0, len(ids), 400):
        for candidate, row_number in (
            db.query(MatchCandidate, SourceRecord.row_number)
            .join(SourceRecord, SourceRecord.id == MatchCandidate.target_record_id)
            .filter(MatchCandidate.id.in_(ids[offset : offset + 400]))
        ):
            selections.append(
                {
                    "record_id": candidate.target_record_id,
                    "row_number": row_number,
                    "idpel": candidate.candidate_idpel,
                    "distance_meters": candidate.distance_meters,
                    "method": methods[candidate.target_record_id],
                }
            )
    row_numbers = {item["record_id"]: item["row_number"] for item in base["unpaired"]}
    for record, candidate in additions.items():
        selections.append(
            {
                "record_id": record,
                "row_number": row_numbers[record],
                "idpel": candidate["idpel"],
                "distance_meters": candidate["distance_meters"],
                "method": "expanded_radius",
            }
        )
    selections.sort(key=lambda item: (item["row_number"], item["record_id"]))
    identities = [item["idpel"] for item in selections]
    if len(identities) != len(set(identities)) or set(identities).intersection(
        identity_owners(db, process_id)
    ):
        raise HTTPException(409, "Pasangan IDPEL tidak unik. Muat ulang pratinjau.")
    digest = hashlib.sha256(
        json.dumps(
            [
                base["fingerprint"],
                "complete_v1",
                req.max_radius_meters,
                sorted(selected.items()),
                additions,
                remaining,
            ],
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "generation": run.generation,
        "radius_meters": req.radius_meters,
        "max_radius_meters": req.max_radius_meters,
        "result_radius_meters": result_radius,
        "total_targets": base["total_targets"],
        "protected_count": base["protected_count"],
        "selected_count": len(selections),
        "nearest_count": len(base["_selected"]),
        "equal_distance_count": len(base["_suggestions"]),
        "expanded_count": sum(
            method == "expanded_radius" for method in methods.values()
        ),
        "unpaired_count": len(remaining),
        "unpaired": remaining,
        "unpaired_reasons": dict(Counter(item["reason"] for item in remaining)),
        "selections": selections,
        "fingerprint": digest,
        "creates_version": result_radius > run.radius_meters or bool(additions),
        "_selected": selected,
        "_additions": additions,
        "_methods": methods,
        "_expanded_records": expanded_records,
        "_version": base["_version"],
    }


@router.post("/{kind}/checks/{process_id}/automatic/complete/preview")
def preview_complete(
    kind: CorrectionKind, process_id: int, req: CompleteRequest, db: DbSession
):
    return public_plan(complete_plan(db, kind, process_id, req))


def signature(req: CompleteApply) -> str:
    return json.dumps(
        [req.generation, req.radius_meters, req.max_radius_meters, req.fingerprint],
        separators=(",", ":"),
    )


def operation_key(req: CompleteApply) -> str:
    return "complete_" + hashlib.sha256(req.request_key.encode()).hexdigest()[:32] + "_"


def replay_complete(
    db: Session, process_id: int, req: CompleteApply, actor: str
) -> dict[str, Any] | None:
    event = (
        db.query(CorrectionDecision)
        .filter(
            CorrectionDecision.request_key.startswith(
                operation_key(req), autoescape=True
            )
        )
        .first()
    )
    if event:
        metadata = event.candidate.get("automatic_selection", {})
        if (
            event.process_id != process_id
            or event.actor != actor
            or metadata.get("signature") != signature(req)
        ):
            raise HTTPException(
                409, "Kunci permintaan sudah digunakan untuk pilihan berbeda"
            )
        return {**metadata["result"], "already_applied": True}
    for run in (
        db.query(MatchingRun)
        .filter_by(process_id=process_id)
        .order_by(MatchingRun.generation.desc())
    ):
        operation = (run.processing or {}).get("complete_operation", {})
        if operation.get("key") == operation_key(req):
            if operation["signature"] != signature(req) or operation["actor"] != actor:
                raise HTTPException(
                    409, "Kunci permintaan sudah digunakan untuk pilihan berbeda"
                )
            return {**operation["result"], "already_applied": True}
    return None


def extension_run(
    db: Session, process: ReconciliationProcess, base: MatchingRun, plan: dict[str, Any]
) -> MatchingRun:
    now = utc_now()
    run = MatchingRun(
        process_id=process.id,
        generation=base.generation + 1,
        candidate_policy=base.candidate_policy,
        status=ProcessStatus.COMPLETED,
        radius_meters=max(base.radius_meters, plan["result_radius_meters"]),
        max_candidates=base.max_candidates,
        total_targets=base.total_targets,
        matched_targets=base.matched_targets,
        created_at=now,
        completed_at=now,
    )
    db.add(run)
    db.flush()
    columns = [
        column.name
        for column in CorrectionTarget.__table__.columns
        if column.name not in {"id", "run_id"}
    ]
    db.execute(
        insert(CorrectionTarget.__table__).from_select(
            ["run_id", *columns],
            select(
                literal(run.id),
                *(CorrectionTarget.__table__.c[name] for name in columns),
            ).where(CorrectionTarget.run_id == base.id),
        )
    )
    # Only new chosen candidates are appended. All previous alternatives remain
    # available through immutable inherited generations, including in the map.
    inherited = candidate_generations(base)
    run.processing = {
        "state": "ready",
        "stage": "done",
        "revision": 1,
        "total_rows": base.total_targets,
        "processed_rows": base.total_targets,
        "validated_rows": base.total_targets,
        "matched_rows": base.matched_targets,
        "last_source_id": db.query(func.max(CorrectionTarget.source_record_id))
        .filter_by(run_id=base.id)
        .scalar()
        or 0,
        "last_row_number": db.query(func.max(SourceRecord.row_number))
        .join(CorrectionTarget, CorrectionTarget.source_record_id == SourceRecord.id)
        .filter(CorrectionTarget.run_id == base.id)
        .scalar(),
        "started_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "elapsed_seconds": 0,
        "stage_elapsed_seconds": 0,
        "stage_timed_rows": 0,
        "error": None,
        "inherited_candidate_generations": inherited,
        "automatic_extension": {
            "base_generation": base.generation,
            "base_radius_meters": base.radius_meters,
            "search_radius_meters": plan["result_radius_meters"],
            "target_count": len(plan["_expanded_records"]),
            "added_count": len(plan["_additions"]),
        },
    }
    run.processing = {
        **run.processing,
        "last_validated_source_id": run.processing["last_source_id"],
    }
    process.current_generation = run.generation
    process.radius_meters = run.radius_meters
    process.matching_status = ProcessStatus.COMPLETED
    process.completed_at = now
    return run


@router.post("/{kind}/checks/{process_id}/automatic/complete/apply")
def apply_complete(
    kind: CorrectionKind,
    process_id: int,
    req: CompleteApply,
    db: DbSession,
    actor: CurrentActor,
):
    started = monotonic()
    check_process(db, kind, process_id)
    replay = replay_complete(db, process_id, req, actor)
    if replay:
        return replay
    plan = complete_plan(db, kind, process_id, req)
    if plan["fingerprint"] != req.fingerprint:
        raise HTTPException(
            409, "Pilihan atau kandidat berubah. Buat pratinjau lengkap ulang."
        )
    db.rollback()
    try:
        lock_review_session(db)
        db.query(ReconciliationProcess).filter_by(
            id=process_id
        ).populate_existing().with_for_update().one()
        replay = replay_complete(db, process_id, req, actor)
        if replay:
            return replay
        process, base = writable_run(db, kind, process_id, req)
        pinned_sources(db, process)
        if decision_version(db, process_id) != plan["_version"]:
            raise HTTPException(
                409, "Pilihan berubah saat menyimpan. Buat pratinjau lengkap ulang."
            )
        run = (
            extension_run(db, process, base, plan) if plan["creates_version"] else base
        )
        selected = dict(plan["_selected"])
        for record, details in plan["_additions"].items():
            target = (
                db.query(CorrectionTarget)
                .filter_by(run_id=run.id, source_record_id=record)
                .one()
            )
            master = db.get(MasterSisaRecord, details["master_record_id"])
            if (
                master is None
                or master.snapshot_id != process.master_snapshot_id
                or master.idpel != details["idpel"]
            ):
                raise HTTPException(409, "Identitas master tidak sesuai bukti kandidat")
            rank = (
                db.query(func.max(MatchCandidate.rank))
                .filter(
                    candidate_scope(base), MatchCandidate.target_record_id == record
                )
                .scalar()
                or 0
            ) + 1
            fields = {
                **details["fields"],
                "source_record_id": details["source"]["record_id"],
            }
            candidate = MatchCandidate(
                process_id=process_id,
                generation=run.generation,
                target_record_id=record,
                target_ref=str(
                    target.fields.get("target_ref")
                    or target.fields.get("idpel")
                    or record
                ),
                target_lat=target.fields["lat"],
                target_lon=target.fields["lon"],
                candidate_idpel=details["idpel"],
                candidate_nama=fields.get("nama"),
                candidate_lat=fields["lat"],
                candidate_lon=fields["lon"],
                distance_meters=details["distance_meters"],
                rank=rank,
                jenis_layanan=master.jenis_layanan,
                validity_status="VALID",
                is_under_5m=int(details["distance_meters"] < 5),
                is_accepted=0,
            )
            db.add(candidate)
            db.flush()
            db.add(
                CorrectionCandidateEvidence(
                    candidate_id=candidate.id,
                    master_record_id=master.id,
                    fields=fields,
                    observations=[{**details["source"], "fields": fields}],
                )
            )
            selected[record] = candidate.id
            if target.search_status == "no_candidates":
                run.matched_targets += 1
            target.search_status = "matched"
            target.candidate_count += 1
        db.flush()
        result = {
            "selected_count": len(selected),
            "generation": run.generation,
            "radius_meters": plan["result_radius_meters"],
            "unpaired_count": plan["unpaired_count"],
            "created_version": run.id != base.id,
        }
        used = set(identity_owners(db, process_id))
        ids = list(selected.values())
        for offset in range(0, len(ids), 200):
            chunk = ids[offset : offset + 200]
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
                .filter(candidate_scope(run), MatchCandidate.id.in_(chunk))
                .all()
            )
            if len(rows) != len(chunk):
                raise HTTPException(
                    409, "Bukti kandidat belum lengkap; penyimpanan dibatalkan"
                )
            events = []
            for candidate, evidence, target in rows:
                if (
                    candidate.candidate_idpel in used
                    or candidate.candidate_idpel != evidence.fields.get("idpel")
                    or candidate.distance_meters > plan["result_radius_meters"]
                ):
                    raise HTTPException(
                        409,
                        "Identitas atau radius kandidat tidak sesuai; penyimpanan dibatalkan",
                    )
                used.add(candidate.candidate_idpel)
                events.append(
                    {
                        "process_id": process_id,
                        "target_record_id": target.source_record_id,
                        "generation": run.generation,
                        "revision": 1,
                        "candidate_id": candidate.id,
                        "request_key": operation_key(req)
                        + str(target.source_record_id),
                        "actor": actor,
                        "reason": f"Pilihan otomatis lengkap; satu IDPEL satu target; radius awal {req.radius_meters:g} m; batas {req.max_radius_meters:g} m; identitas belum diverifikasi; pratinjau {req.fingerprint}",
                        "target_fields": target.fields,
                        "candidate": {
                            "id": candidate.id,
                            "rank": candidate.rank,
                            "distance_meters": candidate.distance_meters,
                            "fields": evidence.fields,
                            "observations": evidence.observations,
                            "automatic_selection": {
                                "mode": "complete",
                                "method": plan["_methods"][target.source_record_id],
                                "identity_verified": False,
                                "signature": signature(req),
                                "result": result,
                            },
                        },
                    }
                )
            db.bulk_insert_mappings(CorrectionDecision.__mapper__, events)
            db.query(MatchCandidate).filter(MatchCandidate.id.in_(chunk)).update(
                {"is_accepted": 1}, synchronize_session=False
            )
        if selected:
            process.review_status = ReviewStatus.IN_PROGRESS
        process.total_targets, process.matched_targets = (
            run.total_targets,
            run.matched_targets,
        )
        process.unmatched_targets = run.total_targets - run.matched_targets
        if run.id != base.id:
            run.processing = {
                **run.processing,
                "matched_rows": run.matched_targets,
                "elapsed_seconds": monotonic() - started,
                "updated_at": utc_now().isoformat(),
                "complete_operation": {
                    "key": operation_key(req),
                    "actor": actor,
                    "signature": signature(req),
                    "result": result,
                },
            }
        db.commit()
        return {**result, "already_applied": False}
    except SQLAlchemyError as exc:
        raise database_write_error(
            db, exc, "penyimpanan pilihan otomatis lengkap"
        ) from exc
    except Exception:
        db.rollback()
        raise
