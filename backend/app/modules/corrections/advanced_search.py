"""Find identity evidence in pinned eligible masters without altering saved searches."""

import math
from typing import Any, Literal

from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.correction_decision import CorrectionDecision
from app.models.master_sisa import (
    CorrectionObservationCatalog,
    MasterPreparation,
    MasterSisaRecord,
    MasterSnapshot,
)
from app.models.matching import MatchCandidate
from app.models.upload import SourceRecord
from app.modules.corrections.automatic import DbSession, PreviewRequest, writable_run
from app.modules.corrections.export_data import coordinate_sources
from app.modules.corrections.selection_state import current_choices
from app.modules.corrections.service import (
    CorrectionKind,
    check_process,
    reference_value,
    selected_run,
)
from app.modules.spatial.engine import calculate_haversine_distance
from app.modules.spatial.master_evidence import candidate_observations
from app.modules.spatial.master_preparation import source_spec
from app.search_index import prepare_search, search_candidates
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

router = APIRouter()
SearchField = Literal["idpel", "meter", "nama", "gardu"]
METER_KEYS = ("meter_ref", "nomor_meter_kwh", "nomor_meter_prepaid")


def comparable(value: Any) -> str:
    text = " ".join(str(value or "").split()).casefold()
    return text if text not in {"", "-", "0"} else ""


def pinned_sources(db: Session, process: Any) -> list[int]:
    snapshot = db.get(MasterSnapshot, process.master_snapshot_id)
    if snapshot is None or not snapshot.ready:
        raise HTTPException(409, "Master sisa pemeriksaan belum siap")
    try:
        specs = source_spec(db, process)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    catalog = db.get(CorrectionObservationCatalog, snapshot.id)
    prepared = db.query(MasterPreparation).filter_by(snapshot_id=snapshot.id).first()
    original = (catalog.processing.get("sources") if catalog else None) or (
        prepared.sources if prepared else None
    )
    if original and (
        {item["id"] for item in original} != {item["id"] for item in specs}
        or any(
            not any(
                old["id"] == spec["id"]
                and old["mapping"] == spec["mapping"]
                and old["catalog_version"] == spec["catalog_version"]
                for old in original
            )
            for spec in specs
        )
    ):
        raise HTTPException(
            409,
            "Mapping sumber master berubah. Buat pemeriksaan baru sebelum mencari kandidat lanjutan.",
        )
    return [spec["id"] for spec in specs]


def coordinate_distance(target: dict[str, Any], fields: dict[str, Any]) -> float | None:
    values = [
        target.get("lat"),
        target.get("lon"),
        fields.get("lat"),
        fields.get("lon"),
    ]
    if any(
        value is None or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in values
    ):
        return None
    if not all(-90 <= value <= 90 for value in (values[0], values[2])) or not all(
        -180 <= value <= 180 for value in (values[1], values[3])
    ):
        return None
    return calculate_haversine_distance(*values)


def matches(fields: dict[str, Any], field: SearchField, q: str) -> bool:
    if field == "idpel":
        return fields.get("idpel") == q
    if field == "meter":
        return any(
            reference_value(fields.get(key)) == reference_value(q) for key in METER_KEYS
        )
    if field == "gardu":
        return comparable(fields.get("kode_gardu")) == comparable(q)
    return comparable(q) in comparable(fields.get("nama"))


@router.get("/{kind}/checks/{process_id}/records/{record_id}/advanced-candidates")
def advanced_candidates(
    kind: CorrectionKind,
    process_id: int,
    record_id: int,
    db: DbSession,
    generation: int = Query(ge=1),
    radius_meters: float = Query(gt=0, le=100000, allow_inf_nan=False),
    field: SearchField = "meter",
    q: str = Query(min_length=3, max_length=100),
    skip: int = Query(0, ge=0, le=100000),
    limit: int = Query(10, ge=1, le=20),
) -> dict[str, Any]:
    q = q.strip()
    if len(q) < 3 or any(ord(character) < 32 for character in q):
        raise HTTPException(422, "Isi sedikitnya 3 karakter pencarian yang valid")
    if field in {"meter", "idpel"} and reference_value(q) is None:
        raise HTTPException(
            422, "Identitas pencarian tidak boleh kosong atau seluruhnya nol"
        )
    _, process = check_process(db, kind, process_id)
    run = selected_run(db, process, generation)
    assert run is not None
    writable_run(
        db,
        kind,
        process_id,
        PreviewRequest(generation=generation, radius_meters=radius_meters),
    )
    target = (
        db.query(CorrectionTarget)
        .filter_by(run_id=run.id, source_record_id=record_id)
        .one_or_none()
    )
    if target is None:
        raise HTTPException(404, "Target tidak ditemukan pada versi pemeriksaan ini")
    source_ids = pinned_sources(db, process)
    identity = CorrectionDecision.candidate["fields"]["idpel"].as_string()
    used_query = (
        current_choices(db, process_id)
        .filter(
            CorrectionDecision.candidate_id.is_not(None),
            CorrectionDecision.target_record_id != record_id,
            identity.is_not(None),
        )
        .with_entities(identity)
    )
    used = {value for (value,) in used_query}
    more_identities = False
    if field == "idpel":
        wanted = [q] if skip == 0 else []
    else:
        state = prepare_search(db, ("source",))
        if state and not state["ready"]:
            return {"items": [], "has_more": False, "search_index": state, "skip": skip}
        pattern = (
            "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        predicate = (
            or_(
                *(
                    func.upper(SourceRecord.normalized_data[key].as_string())
                    == q.upper()
                    for key in METER_KEYS
                )
            )
            if field == "meter"
            else func.upper(SourceRecord.normalized_data["kode_gardu"].as_string())
            == q.upper()
            if field == "gardu"
            else SourceRecord.normalized_data["nama"]
            .as_string()
            .ilike(pattern, escape="\\")
        )
        matching = db.query(SourceRecord.idpel).filter(
            SourceRecord.batch_id.in_(source_ids),
            SourceRecord.is_valid.is_(True),
            SourceRecord.idpel.is_not(None),
            search_candidates(db, (("source", SourceRecord.id),), q),
            predicate,
        )
        wanted = [
            value
            for (value,) in matching.distinct()
            .order_by(SourceRecord.idpel)
            .offset(skip)
            .limit(201)
        ]
        more_identities = len(wanted) > 200
        wanted = wanted[:200]
    # Look up identities using the existing IDPEL index, then scope the small
    # result in Python. SQLite otherwise chooses a full million-row snapshot scan.
    eligible = (
        {
            master.idpel: master
            for master in db.query(MasterSisaRecord).filter(
                MasterSisaRecord.idpel.in_(wanted)
            )
            if master.snapshot_id == process.master_snapshot_id
            and master.idpel not in used
        }
        if wanted
        else {}
    )
    matches_in_page = [eligible[value] for value in wanted if value in eligible]
    has_more = more_identities or len(matches_in_page) > limit
    masters = matches_in_page[:limit]
    next_skip = (
        skip + wanted.index(masters[-1].idpel) + 1
        if len(matches_in_page) > limit
        else skip + len(wanted)
    )
    originals = (
        dict(
            db.query(SourceRecord.id, SourceRecord.data)
            .filter(
                SourceRecord.id.in_([master.source_record_id for master in masters])
            )
            .all()
        )
        if masters
        else {}
    )
    observations = candidate_observations(db, originals)
    stored = (
        {
            candidate.candidate_idpel: (candidate, evidence)
            for candidate, evidence in db.query(
                MatchCandidate, CorrectionCandidateEvidence
            )
            .join(
                CorrectionCandidateEvidence,
                CorrectionCandidateEvidence.candidate_id == MatchCandidate.id,
            )
            .filter(
                MatchCandidate.process_id == process_id,
                MatchCandidate.generation == generation,
                MatchCandidate.target_record_id == record_id,
                MatchCandidate.candidate_idpel.in_(
                    [master.idpel for master in masters]
                ),
            )
            .order_by(MatchCandidate.rank)
        }
        if masters
        else {}
    )
    items = []
    for master in masters:
        original = originals.get(master.source_record_id) or {}
        evidence_rows = observations.get(master.source_record_id, [])
        # Keep evidence pinned even for legacy embedded observation lists.
        evidence_rows = [row for row in evidence_rows if row["batch_id"] in source_ids]
        matched = [row for row in evidence_rows if matches(row["fields"], field, q)]
        if not matched and field != "idpel":
            continue
        locations = [
            (distance, row)
            for row in evidence_rows
            if (distance := coordinate_distance(target.fields, row["fields"]))
            is not None
        ]
        nearest = (
            min(locations, key=lambda item: (item[0], item[1]["record_id"]))
            if locations
            else None
        )
        fields = {
            key: value
            for key, value in original.items()
            if key not in {"source_observations", "source_observation_batches"}
        }
        if nearest:
            fields.update(
                {
                    key: value
                    for key, value in nearest[1]["fields"].items()
                    if value not in (None, "")
                }
            )
        distance = nearest[0] if nearest else None
        saved = stored.get(master.idpel)
        candidate = None
        coordinate_source = nearest[1] if nearest else None
        if saved:
            row, proof = saved
            fields, distance = proof.fields, row.distance_meters
            sources = coordinate_sources(
                {"fields": proof.fields, "observations": proof.observations}
            )
            coordinate_source = sources[0] if sources else None
            if target.search_status == "matched" and distance <= radius_meters:
                candidate = {
                    "id": row.id,
                    "rank": row.rank,
                    "distance_meters": distance,
                    "fields": proof.fields,
                    "observations": proof.observations,
                    "is_accepted": row.is_accepted,
                    "used_by": [],
                }
        reasons = [
            {
                "idpel": "IDPEL sumber sama dengan pencarian",
                "meter": "Nomor meter sumber sama dengan pencarian",
                "nama": "Nama sumber memuat teks pencarian",
                "gardu": "Kode gardu sumber sama dengan pencarian",
            }[field]
        ]
        target_meters = {
            value
            for key in METER_KEYS
            if (value := reference_value(target.fields.get(key)))
        }
        meter_match = (
            any(
                target_meters.intersection(
                    reference_value(row["fields"].get(key)) for key in METER_KEYS
                )
                for row in evidence_rows
            )
            if target_meters
            else False
        )
        if meter_match:
            reasons.append("Nomor meter cocok dengan data target")
        for key, label in (
            ("nama", "Nama"),
            ("alamat", "Alamat"),
            ("kode_gardu", "Gardu"),
        ):
            value = comparable(target.fields.get(key))
            if value and any(
                comparable(row["fields"].get(key)) == value for row in evidence_rows
            ):
                reasons.append(f"{label} sama dengan data target")
        action = (
            "choose"
            if candidate
            else "missing_coordinates"
            if distance is None
            else "expand_search"
            if distance > run.radius_meters
            else "change_filter"
            if distance > radius_meters
            else "rerun_search"
        )
        if target.search_status not in {"matched", "no_candidates"}:
            candidate, action = None, "fix_target"
        items.append(
            {
                "idpel": master.idpel,
                "fields": fields,
                "distance_meters": distance,
                "reasons": reasons,
                "target_meter_matches": meter_match,
                "matched_sources": matched,
                "coordinate_source": coordinate_source,
                "candidate": candidate,
                "action": action,
                "suggested_radius_meters": min(
                    100000,
                    max(math.ceil(distance) + 1, math.ceil(run.radius_meters) + 1),
                )
                if action == "expand_search"
                and distance is not None
                and distance < 100000
                else None,
            }
        )
    items.sort(
        key=lambda item: (
            not item["target_meter_matches"],
            item["distance_meters"]
            if item["distance_meters"] is not None
            else math.inf,
            item["idpel"],
        )
    )
    return {
        "items": items,
        "has_more": has_more,
        "skip": skip,
        "next_skip": next_skip if has_more else None,
        "generation": generation,
        "radius_meters": radius_meters,
        "stored_radius_meters": run.radius_meters,
    }
