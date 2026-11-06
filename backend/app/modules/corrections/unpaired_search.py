"""Read-only radius follow-up for targets left out of the current pairing plan."""

import math
from collections import Counter
from itertools import groupby
from typing import Any, Literal, NamedTuple

from app.models.correction import CorrectionTarget
from app.models.master_sisa import (
    CorrectionMasterObservation,
    CorrectionObservationCatalog,
    MasterSisaRecord,
)
from app.models.matching import MatchCandidate
from app.models.upload import SourceRecord, UploadBatch
from app.modules.corrections.advanced_search import coordinate_distance, pinned_sources
from app.modules.corrections.automatic import (
    DbSession,
    PreviewRequest,
    build_plan,
    decision_version,
    writable_run,
)
from app.modules.corrections.export_data import result_columns
from app.modules.corrections.observations import ALL_OBSERVATIONS_POLICY
from app.modules.corrections.selection_state import identity_owners
from app.modules.corrections.service import CorrectionKind
from app.modules.corrections.spreadsheet import (
    CANDIDATE_DISTANCE_HEADER,
    DISTANCE_NUMBER_FORMAT,
    RESULT_HEADERS,
    RESULT_WIDTHS,
    Spreadsheet,
)
from app.modules.corrections.tie_suggestions import equal_distance_matching
from app.modules.spatial.master_preparation import cached_fields
from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import or_

router = APIRouter()


class UnpairedRequest(PreviewRequest):
    tie_strategy: Literal["suggest"] = "suggest"
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    search_radius_meters: float = Field(gt=0, le=5000)


class Edge(NamedTuple):
    distance: float
    record: int
    identity: str
    source: int
    latitude: float
    longitude: float


@router.post("/{kind}/checks/{process_id}/automatic/unpaired-search")
def search_unpaired(
    kind: CorrectionKind, process_id: int, req: UnpairedRequest, db: DbSession
) -> dict[str, Any]:
    if req.search_radius_meters <= req.radius_meters:
        raise HTTPException(
            422, "Radius lanjutan harus lebih besar dari radius pilihan"
        )
    process, run = writable_run(db, kind, process_id, req)
    plan = build_plan(db, kind, process_id, req)
    if req.fingerprint != plan["fingerprint"]:
        raise HTTPException(409, "Pilihan atau usulan berubah. Muat ulang pratinjau.")
    remaining = {item["record_id"]: item for item in plan["unpaired"]}
    if len(remaining) > 500:
        raise HTTPException(
            422,
            "Selesaikan tinjauan hingga paling banyak 500 target tanpa pasangan sebelum pencarian lanjutan.",
        )
    source_ids = pinned_sources(db, process)
    all_locations = run.candidate_policy == ALL_OBSERVATIONS_POLICY
    if all_locations:
        catalog = db.get(CorrectionObservationCatalog, process.master_snapshot_id)
        if catalog is None or not catalog.processing.get("ready"):
            raise HTTPException(
                409, "Indeks lokasi master belum siap pada pemeriksaan ini"
            )
    reserved = set(identity_owners(db, process_id))
    candidate_ids = [*plan["_selected"].values(), *plan["_suggestions"].values()]
    for offset in range(0, len(candidate_ids), 400):
        reserved.update(
            identity
            for (identity,) in db.query(MatchCandidate.candidate_idpel).filter(
                MatchCandidate.id.in_(candidate_ids[offset : offset + 400])
            )
        )
    targets = (
        db.query(CorrectionTarget)
        .filter(
            CorrectionTarget.run_id == run.id,
            CorrectionTarget.source_record_id.in_(remaining),
        )
        .all()
    )
    edges: list[Edge] = []
    available: Counter[int] = Counter()
    blocked: dict[int, str] = {}
    delta = math.degrees(req.search_radius_meters / 6371000)
    for target in targets:
        record, fields = target.source_record_id, target.fields
        if target.search_status not in {"matched", "no_candidates"}:
            blocked[record] = "fix_target"
            continue
        if coordinate_distance(fields, fields) is None:
            blocked[record] = "missing_coordinates"
            continue
        lat, lon = fields["lat"], fields["lon"]
        if all_locations:
            locations = (
                db.query(
                    MasterSisaRecord.idpel,
                    CorrectionMasterObservation.source_record_id,
                    CorrectionMasterObservation.latitude,
                    CorrectionMasterObservation.longitude,
                )
                .select_from(CorrectionMasterObservation)
                .join(
                    MasterSisaRecord,
                    MasterSisaRecord.id == CorrectionMasterObservation.master_record_id,
                )
                .filter(
                    CorrectionMasterObservation.snapshot_id
                    == process.master_snapshot_id,
                    MasterSisaRecord.snapshot_id == process.master_snapshot_id,
                    CorrectionMasterObservation.latitude.between(
                        lat - delta, lat + delta
                    ),
                )
            )
        else:
            locations = db.query(
                MasterSisaRecord.idpel,
                MasterSisaRecord.source_record_id,
                MasterSisaRecord.latitude,
                MasterSisaRecord.longitude,
            ).filter(
                MasterSisaRecord.snapshot_id == process.master_snapshot_id,
                MasterSisaRecord.latitude.between(lat - delta, lat + delta),
            )
        # Bound longitude before joining/loading nearby identities. A latitude
        # strip alone spans the entire country and can read millions of locations.
        if abs(lat) + delta < 90:
            width = math.degrees(
                math.asin(
                    min(1, math.sin(math.radians(delta)) / math.cos(math.radians(lat)))
                )
            )
            longitude = (
                CorrectionMasterObservation.longitude
                if all_locations
                else MasterSisaRecord.longitude
            )
            low, high = lon - width, lon + width
            locations = locations.filter(
                or_(longitude >= low + 360, longitude <= high)
                if low < -180
                else or_(longitude >= low, longitude <= high - 360)
                if high > 180
                else longitude.between(low, high)
            )
        nearest: dict[str, Edge] = {}
        for identity, source, y, x in locations:
            if identity in reserved or source is None:
                continue
            distance = coordinate_distance(fields, {"lat": y, "lon": x})
            if distance is None or distance > req.search_radius_meters:
                continue
            edge = Edge(distance, record, identity, source, y, x)
            if identity not in nearest or edge < nearest[identity]:
                nearest[identity] = edge
        available[record] = len(nearest)
        edges.extend(nearest.values())
        if len(edges) > 200000:
            raise HTTPException(
                422,
                "Kandidat terlalu banyak. Gunakan radius lanjutan yang lebih kecil.",
            )
    chosen: dict[int, Edge] = {}
    used = set(reserved)
    for _, bucket in groupby(sorted(edges), key=lambda edge: edge.distance):
        graph: dict[int, dict[str, Edge]] = {}
        for edge in bucket:
            if edge.record not in chosen and edge.identity not in used:
                graph.setdefault(edge.record, {})[edge.identity] = edge
        for record, identity in equal_distance_matching(graph).items():
            chosen[record] = graph[record][identity]
            used.add(identity)
    originals = {
        source.id: source
        for source in db.query(SourceRecord).filter(
            SourceRecord.id.in_({edge.source for edge in chosen.values()})
        )
    }
    batches = {
        batch.id: batch
        for batch in db.query(UploadBatch).filter(
            UploadBatch.id.in_({row.batch_id for row in originals.values()})
        )
    }
    items = []
    for item in plan["unpaired"]:
        record = item["record_id"]
        edge = chosen.get(record)
        candidate = None
        if edge:
            source = originals.get(edge.source)
            batch = batches.get(source.batch_id) if source else None
            if source is None or batch is None:
                raise HTTPException(409, "Bukti sumber kandidat belum lengkap")
            fields = cached_fields(source, batch) or dict(source.data or {})
            stored = (
                db.query(MatchCandidate.id)
                .filter_by(
                    process_id=process_id,
                    generation=run.generation,
                    target_record_id=record,
                    candidate_idpel=edge.identity,
                )
                .first()
                if edge.distance <= run.radius_meters
                else None
            )
            candidate = {
                "idpel": edge.identity,
                "distance_meters": edge.distance,
                "fields": {
                    **fields,
                    "idpel": edge.identity,
                    "lat": edge.latitude,
                    "lon": edge.longitude,
                },
                "source": {
                    "batch_id": batch.id,
                    "filename": batch.filename,
                    "source_sheet": batch.source_sheet,
                    "row_number": source.row_number,
                    "dataset_type": batch.dataset_type.value,
                    "pinned_source": batch.id in source_ids,
                },
                "action": "expand_search"
                if edge.distance > run.radius_meters
                else "change_filter"
                if stored
                else "rerun_search",
                "suggested_radius_meters": max(
                    math.ceil(edge.distance) + 1, math.ceil(run.radius_meters) + 1
                )
                if edge.distance > run.radius_meters
                else None,
                "needs_verification": True,
            }
        reason = (
            "candidate_found"
            if candidate
            else blocked.get(record)
            or ("shared_candidates" if available[record] else "no_available_idpel")
        )
        items.append(
            {
                **item,
                "reason": reason,
                "available_count": available[record],
                "candidate": candidate,
            }
        )
    if decision_version(db, process_id) != plan["_version"]:
        raise HTTPException(
            409, "Pilihan berubah selama pencarian. Muat ulang pratinjau."
        )
    return {
        "fingerprint": plan["fingerprint"],
        "search_radius_meters": req.search_radius_meters,
        "stored_radius_meters": run.radius_meters,
        "searched_count": len(items),
        "found_count": len(chosen),
        "unpaired_count": len(items) - len(chosen),
        "reason_counts": dict(Counter(item["reason"] for item in items)),
        "items": items,
    }


@router.post("/{kind}/checks/{process_id}/automatic/unpaired-search/export")
def export_unpaired(
    kind: CorrectionKind, process_id: int, req: UnpairedRequest, db: DbSession
):
    result = search_unpaired(kind, process_id, req, db)
    process, run = writable_run(db, kind, process_id, req)
    batch = db.get(UploadBatch, process.target_batch_id)
    assert batch is not None
    book = Spreadsheet()
    sheet = book.sheet(
        "Usulan Lanjutan",
        [*RESULT_HEADERS, "Status Usulan", "Baris Target", "Radius Tersimpan (m)"],
        [*RESULT_WIDTHS, 28, 18, 24],
        number_formats={CANDIDATE_DISTANCE_HEADER: DISTANCE_NUMBER_FORMAT},
    )
    wanted = {
        item["record_id"]: item["candidate"]
        for item in result["items"]
        if item["candidate"]
    }
    for source, target in (
        db.query(SourceRecord, CorrectionTarget)
        .join(CorrectionTarget, CorrectionTarget.source_record_id == SourceRecord.id)
        .filter(CorrectionTarget.run_id == run.id, SourceRecord.id.in_(wanted))
        .order_by(SourceRecord.row_number, SourceRecord.id)
    ):
        candidate = wanted[source.id]
        observation = {**candidate["source"], "fields": candidate["fields"]}
        snapshot = {
            "fields": candidate["fields"],
            "observations": [observation],
            "distance_meters": candidate["distance_meters"],
        }
        book.append(
            sheet,
            [
                *result_columns(
                    source,
                    batch,
                    target.fields,
                    snapshot,
                    radius_meters=req.search_radius_meters,
                ),
                "Perlu verifikasi",
                source.row_number,
                run.radius_meters,
            ],
        )
    return book.response(
        f"usulan_lanjutan_{kind.value}_{process_id}_radius_{req.search_radius_meters:g}m_v{run.generation}.xlsx"
    )
