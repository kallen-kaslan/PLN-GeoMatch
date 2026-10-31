"""Index all eligible source coordinates once, with bounded durable checkpoints."""

import math
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session, load_only

from app.models.master_sisa import (
    CorrectionMasterObservation,
    CorrectionObservationCatalog,
    MasterSisaRecord,
    MasterSnapshot,
)
from app.models.matching import ReconciliationProcess
from app.models.upload import SourceRecord, UploadBatch
from app.modules.spatial.master_preparation import cached_fields, source_spec

ALL_OBSERVATIONS_POLICY = 2
OBSERVATION_CHUNK_ROWS = 4000


def advance_observations(db: Session, process: ReconciliationProcess) -> dict[str, Any]:
    """Never alter canonical master locations, PDPJ exclusions, or previous outcomes."""
    snapshot = (
        db.query(MasterSnapshot)
        .filter_by(id=process.master_snapshot_id)
        .with_for_update()
        .one()
    )
    if not snapshot.ready:
        raise ValueError("Snapshot master belum selesai")
    catalog = db.get(CorrectionObservationCatalog, snapshot.id)
    if catalog is None:
        sources = source_spec(db, process)
        catalog = CorrectionObservationCatalog(
            snapshot_id=snapshot.id,
            processing={
                "sources": sources,
                "file_index": 0,
                "last_source_id": 0,
                "source_total": sum(item["total_rows"] for item in sources),
                "source_rows": 0,
                "observation_rows": 0,
                "ready": False,
            },
        )
        db.add(catalog)
        db.flush()
    state = dict(catalog.processing)
    reused = state["ready"]
    remaining = OBSERVATION_CHUNK_ROWS
    while not state["ready"] and remaining > 0:
        if state["file_index"] == len(state["sources"]):
            state["ready"] = True
            break
        spec = state["sources"][state["file_index"]]
        batch = db.get(UploadBatch, spec["id"])
        assert batch is not None
        if (
            batch.column_mapping != spec["mapping"]
            or batch.catalog_version != spec["catalog_version"]
        ):
            raise ValueError("Mapping master berubah; buat pemeriksaan baru")
        limit = remaining
        rows = (
            db.query(SourceRecord)
            .options(
                load_only(
                    SourceRecord.id,
                    SourceRecord.batch_id,
                    SourceRecord.idpel,
                    SourceRecord.normalized_data,
                    SourceRecord.validation_errors,
                    SourceRecord.is_valid,
                )
            )
            .filter(
                SourceRecord.batch_id == batch.id,
                SourceRecord.id > state["last_source_id"],
            )
            .order_by(SourceRecord.id)
            .limit(remaining)
            .all()
        )
        # Filtering snapshot in Python avoids SQLite choosing a full snapshot scan
        # instead of the existing indexed IDPEL lookup for each small source chunk.
        parsed = [(row, cached_fields(row, batch)) for row in rows]
        masters = {
            master.idpel: master.id
            for master in db.query(MasterSisaRecord).filter(
                MasterSisaRecord.idpel.in_(
                    {fields["idpel"] for _, fields in parsed if fields}
                )
            )
            if master.snapshot_id == snapshot.id
        }
        pending = []
        for row, fields in parsed:
            if fields is None or fields["idpel"] not in masters:
                continue
            lat, lon = fields.get("lat"), fields.get("lon")
            if (
                lat is None
                or lon is None
                or not math.isfinite(lat)
                or not math.isfinite(lon)
                or not -90 <= lat <= 90
                or not -180 <= lon <= 180
            ):
                continue
            pending.append(
                {
                    "snapshot_id": snapshot.id,
                    "master_record_id": masters[fields["idpel"]],
                    "source_record_id": row.id,
                    "latitude": lat,
                    "longitude": lon,
                }
            )
        if pending:
            db.execute(insert(CorrectionMasterObservation), pending)
        state["source_rows"] += len(rows)
        state["observation_rows"] += len(pending)
        remaining -= len(rows)
        if rows:
            state["last_source_id"] = rows[-1].id
        if len(rows) < limit:
            state["file_index"] += 1
            state["last_source_id"] = 0
    catalog.processing = state
    db.flush()
    return {
        "ready": state["ready"],
        "reused": reused,
        "work_total": state["source_total"],
        "work_done": state["source_rows"],
        "observation_rows": state["observation_rows"],
    }
