"""Group unresolved targets using exact saved coordinates and shared IDPELs."""

import hashlib
from collections import Counter
from typing import Any

from app.models.matching import MatchCandidate, MatchingRun
from app.models.upload import SourceRecord
from app.modules.corrections.automatic import (
    DbSession,
    PreviewRequest,
    build_plan,
    writable_run,
)
from app.modules.corrections.selection_state import identity_owners
from app.modules.corrections.service import CorrectionKind
from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

router = APIRouter()


class GroupRequest(PreviewRequest):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def group_review(
    db: Session, run: MatchingRun, radius: float, plan: dict[str, Any]
) -> list[dict[str, Any]]:
    owners = identity_owners(db, run.process_id)
    assigned = set(owners)
    proposed: dict[str, int] = {}
    selections = list(plan["_selected"].values())
    for offset in range(0, len(selections), 400):
        for identity, record in db.query(
            MatchCandidate.candidate_idpel, MatchCandidate.target_record_id
        ).filter(MatchCandidate.id.in_(selections[offset : offset + 400])):
            assigned.add(identity)
            proposed[identity] = record

    review = {item["record_id"]: item for item in plan["review"]}
    parent = {record: record for record in review}
    tokens: dict[tuple[Any, ...], int] = {}
    evidence: dict[int, list[dict[str, Any]]] = {}

    def root(record: int) -> int:
        while parent[record] != record:
            parent[record] = parent[parent[record]]
            record = parent[record]
        return record

    def connect(record: int, token: tuple[Any, ...]) -> None:
        previous = tokens.setdefault(token, record)
        left, right = root(record), root(previous)
        if left != right:
            parent[max(left, right)] = min(left, right)

    for record, item in review.items():
        focused: list[dict[str, Any]] = []
        if item["reason"] in {"equal_distance", "candidates_used"}:
            distance = None
            # Seek by target/rank and stop after its nearest relevant distance.
            # Source observation JSON is loaded later, only for the opened target.
            rows = (
                db.query(
                    MatchCandidate.candidate_idpel,
                    MatchCandidate.distance_meters,
                    MatchCandidate.candidate_lat,
                    MatchCandidate.candidate_lon,
                )
                .filter(
                    MatchCandidate.process_id == run.process_id,
                    MatchCandidate.generation == run.generation,
                    MatchCandidate.target_record_id == record,
                )
                .order_by(MatchCandidate.rank, MatchCandidate.id)
                .yield_per(64)
            )
            for candidate in rows:
                if candidate.distance_meters > radius:
                    break
                if (
                    item["reason"] == "equal_distance"
                    and candidate.candidate_idpel in assigned
                ):
                    continue
                if distance is not None and candidate.distance_meters != distance:
                    break
                distance = candidate.distance_meters
                identity = candidate.candidate_idpel
                focused.append(
                    {
                        "idpel": identity,
                        "lat": candidate.candidate_lat,
                        "lon": candidate.candidate_lon,
                        "used_by": owners.get(identity, []),
                        "proposed_for": proposed.get(identity),
                    }
                )
                connect(record, ("idpel", identity))
                connect(
                    record,
                    ("coordinate", candidate.candidate_lat, candidate.candidate_lon),
                )
        evidence[record] = focused

    groups: dict[int, dict[str, Any]] = {}
    for record, item in review.items():
        group = groups.setdefault(root(record), {"targets": [], "candidates": {}})
        group["targets"].append(item)
        for candidate in evidence[record]:
            group["candidates"][
                (candidate["idpel"], candidate["lat"], candidate["lon"])
            ] = candidate
    row_numbers: dict[int, int] = {}
    needed = {
        record
        for group in groups.values()
        for candidate in group["candidates"].values()
        for record in candidate["used_by"]
    }
    needed.update(
        candidate["proposed_for"]
        for group in groups.values()
        for candidate in group["candidates"].values()
        if candidate["proposed_for"] is not None
    )
    needed_list = list(needed)
    for offset in range(0, len(needed_list), 400):
        row_numbers.update(
            db.query(SourceRecord.id, SourceRecord.row_number)
            .filter(SourceRecord.id.in_(needed_list[offset : offset + 400]))
            .all()
        )

    result = []
    for group in groups.values():
        targets = sorted(
            group["targets"], key=lambda item: (item["row_number"], item["record_id"])
        )
        candidates = sorted(
            group["candidates"].values(),
            key=lambda item: (item["idpel"], item["lat"], item["lon"]),
        )
        for candidate in candidates:
            candidate["used_by"] = [
                {"record_id": record, "row_number": row_numbers.get(record)}
                for record in candidate["used_by"]
            ]
            proposed_record = candidate["proposed_for"]
            candidate["proposed_for"] = (
                {
                    "record_id": proposed_record,
                    "row_number": row_numbers.get(proposed_record),
                }
                if proposed_record is not None
                else None
            )
        coordinates = sorted(
            {(candidate["lat"], candidate["lon"]) for candidate in candidates}
        )
        result.append(
            {
                "id": hashlib.sha256(
                    ",".join(str(item["record_id"]) for item in targets).encode()
                ).hexdigest()[:24],
                "targets": targets,
                "target_count": len(targets),
                "candidates": candidates,
                "candidate_count": len(
                    {candidate["idpel"] for candidate in candidates}
                ),
                "coordinates": [{"lat": lat, "lon": lon} for lat, lon in coordinates],
                "reason_counts": dict(Counter(item["reason"] for item in targets)),
            }
        )
    return sorted(
        result, key=lambda group: (group["targets"][0]["row_number"], group["id"])
    )


@router.post("/{kind}/checks/{process_id}/automatic/review-groups")
def review_groups(
    kind: CorrectionKind, process_id: int, req: GroupRequest, db: DbSession
) -> dict[str, Any]:
    plan = build_plan(db, kind, process_id, req)
    if plan["fingerprint"] != req.fingerprint:
        raise HTTPException(
            409,
            "Pilihan atau radius telah berubah. Muat ulang pratinjau sebelum meninjau kelompok.",
        )
    _, run = writable_run(db, kind, process_id, req)
    groups = group_review(db, run, req.radius_meters, plan)
    return {
        "fingerprint": plan["fingerprint"],
        "groups": groups,
        "group_count": len(groups),
        "target_count": plan["review_count"],
    }
