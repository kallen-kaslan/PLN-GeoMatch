"""Prepare large master snapshots with bounded memory and atomic checkpoints."""

import hashlib
import json
from typing import Any

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only

from app.models.master_sisa import (
    MasterPreparation,
    MasterPreparationExcluded,
    MasterPreparationIdentity,
    MasterSisaRecord,
    MasterSnapshot,
)
from app.models.matching import ReconciliationProcess
from app.models.pdpj import PdpjReview, PdpjRow
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.pdpj.service import completed_review
from app.modules.spatial.master_builder import observation_period
from app.modules.upload.normalization import (
    NORMALIZATION_VERSION,
    extract_standard_fields,
)

PREPARATION_CHUNK_ROWS = 2000
READ_BLOCK_ROWS = 400


def cached_fields(record: SourceRecord, batch: UploadBatch) -> dict[str, Any] | None:
    """Use versioned normalized imports; parse raw cells only for legacy sources."""
    if not record.is_valid:
        return None
    cached = record.normalized_data
    if batch.catalog_version == NORMALIZATION_VERSION and cached is not None:
        if record.validation_errors:
            return None
        fields = dict(cached)
    else:
        fields = extract_standard_fields(record.data or {}, batch.column_mapping)
        if fields.pop("validation_errors", []):
            return None
    if not fields.get("idpel"):
        return None
    fields["tglbaca"] = fields.get("tglbaca") or batch.period
    return fields


def source_spec(db: Session, process: ReconciliationProcess) -> list[dict[str, Any]]:
    """Pin source order as well as interpretation; equal periods keep the last source."""
    sources = process.source_batches or {}
    result = []
    for kind in ("pascabayar", "prabayar", "dil"):
        for batch_id in dict.fromkeys(sources.get(kind, [])):
            batch = db.get(UploadBatch, batch_id)
            if (
                batch is None
                or batch.dataset_type.value != kind
                or batch.status != BatchStatus.COMPLETED
            ):
                raise ValueError("Sumber master tidak sesuai pemeriksaan")
            total = (
                batch.total_rows
                or db.query(SourceRecord.id).filter_by(batch_id=batch_id).count()
            )
            result.append(
                {
                    "id": batch.id,
                    "kind": kind,
                    "filename": batch.filename,
                    "total_rows": total,
                    "mapping": batch.column_mapping,
                    "period": batch.period,
                    "catalog_version": batch.catalog_version,
                }
            )
    return result


def get_preparation(db: Session, process: ReconciliationProcess) -> MasterPreparation:
    """Share only preparations with exactly the same pinned source interpretation."""
    sources = source_spec(db, process)
    review_id = (process.source_batches or {})["pdpj_review_id"]
    review = completed_review(db, (process.source_batches or {})["pdpj"], review_id)
    signature = hashlib.sha256(
        json.dumps(
            {
                "algorithm": 1,
                "normalization": NORMALIZATION_VERSION,
                "sources": sources,
                "review_id": review.id,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    existing = (
        db.query(MasterPreparation)
        .filter_by(signature=signature)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if existing:
        return existing
    approved_total = db.query(PdpjRow.id).filter_by(review_id=review.id).count()
    pending_after = (
        (review.publication or {}).get("last_source_id")
        if review.source_review_id is not None
        else None
    )
    pending_total = (
        db.query(SourceRecord.id)
        .filter(
            SourceRecord.batch_id == review.batch_id, SourceRecord.id > pending_after
        )
        .count()
        if pending_after is not None
        else 0
    )
    # Older runs already pinned their master/PDPJ sources and may have completed
    # an expensive snapshot before checkpoints existed. Adopt that ready result
    # instead of rebuilding it solely to create cache metadata.
    legacy = None
    wanted_sources = [(source["kind"], source["id"]) for source in sources]
    for previous, snapshot, master in (
        db.query(ReconciliationProcess, MasterSnapshot, UploadBatch)
        .join(
            MasterSnapshot,
            MasterSnapshot.id == ReconciliationProcess.master_snapshot_id,
        )
        .join(UploadBatch, UploadBatch.id == MasterSnapshot.master_batch_id)
        .filter(
            MasterSnapshot.ready.is_(True),
            MasterSnapshot.pdpj_batch_id == review.batch_id,
            UploadBatch.catalog_version == NORMALIZATION_VERSION,
        )
        .order_by(MasterSnapshot.id.desc())
        .all()
    ):
        pinned = previous.source_batches or {}
        previous_sources = [
            (kind, batch_id)
            for kind in ("pascabayar", "prabayar", "dil")
            for batch_id in dict.fromkeys(pinned.get(kind, []))
        ]
        if (
            pinned.get("pdpj_review_id") == review.id
            and previous_sources == wanted_sources
        ):
            legacy = snapshot, master
            break
    try:
        with db.begin_nested():
            if legacy is not None:
                snapshot, master = legacy
                eligible = (
                    db.query(MasterSisaRecord.id)
                    .filter_by(snapshot_id=snapshot.id)
                    .count()
                )
                total = sum(item["total_rows"] for item in sources)
                prepared = MasterPreparation(
                    signature=signature,
                    master_batch_id=master.id,
                    snapshot_id=snapshot.id,
                    pdpj_review_id=review.id,
                    sources=sources,
                    processing={
                        "phase": "ready",
                        "source_total": total,
                        "source_rows": total,
                        "unique_rows": master.total_rows,
                        "cached_rows": 0,
                        "skipped_rows": 0,
                        "file_index": len(sources),
                        "file_count": len(sources),
                        "file_rows": 0,
                        "last_source_id": 0,
                        "pdpj_total": approved_total + pending_total,
                        "pdpj_rows": approved_total + pending_total,
                        "materialized_rows": master.total_rows,
                        "eligible_rows": eligible,
                        "excluded_rows": master.total_rows - eligible,
                        "last_identity_id": 0,
                    },
                )
                db.add(prepared)
                db.flush()
                return prepared
            master = UploadBatch(
                filename="Master gabungan bertahap",
                dataset_type=DatasetType.MASTER,
                status=BatchStatus.PROCESSING,
                catalog_version=NORMALIZATION_VERSION,
            )
            db.add(master)
            db.flush()
            snapshot = MasterSnapshot(
                master_batch_id=master.id, pdpj_batch_id=review.batch_id, ready=False
            )
            db.add(snapshot)
            db.flush()
            prepared = MasterPreparation(
                signature=signature,
                master_batch_id=master.id,
                snapshot_id=snapshot.id,
                pdpj_review_id=review.id,
                sources=sources,
                processing={
                    "phase": "reading",
                    "source_total": sum(item["total_rows"] for item in sources),
                    "source_rows": 0,
                    "unique_rows": 0,
                    "cached_rows": 0,
                    "skipped_rows": 0,
                    "file_index": 0,
                    "file_count": len(sources),
                    "file_rows": 0,
                    "last_source_id": 0,
                    "pdpj_total": approved_total + pending_total,
                    "pdpj_rows": 0,
                    "last_review_row_id": 0,
                    "pending_after": pending_after,
                    "last_pending_source_id": pending_after or 0,
                    "reserving_pending": False,
                    "materialized_rows": 0,
                    "last_identity_id": 0,
                    "eligible_rows": 0,
                    "excluded_rows": 0,
                },
            )
            db.add(prepared)
            db.flush()
        return prepared
    except IntegrityError:
        # Another process may have reserved the same signature concurrently.
        existing = (
            db.query(MasterPreparation)
            .filter_by(signature=signature)
            .with_for_update()
            .populate_existing()
            .first()
        )
        if existing is None:
            raise
        return existing


def read_source_chunk(
    db: Session, prepared: MasterPreparation, state: dict[str, Any], limit: int
) -> int:
    """Retain just winning record pointers; all observations remain in raw storage."""
    if state["file_index"] >= len(prepared.sources):
        state["phase"] = "reserving"
        return 0
    item = prepared.sources[state["file_index"]]
    batch = db.get(UploadBatch, item["id"])
    assert batch is not None
    records = (
        db.query(SourceRecord)
        .options(
            load_only(
                SourceRecord.id,
                SourceRecord.batch_id,
                SourceRecord.normalized_data,
                SourceRecord.is_valid,
                SourceRecord.validation_errors,
                SourceRecord.row_number,
                SourceRecord.idpel,
            )
        )
        .filter(
            SourceRecord.batch_id == batch.id, SourceRecord.id > state["last_source_id"]
        )
        .order_by(SourceRecord.id)
        .limit(limit)
        .all()
    )
    values = []
    for offset, record in enumerate(records):
        if record.row_number is None:
            record.row_number = state.get("file_rows", 0) + offset + 2
        fields = cached_fields(record, batch)
        if fields is None:
            state["skipped_rows"] += 1
            continue
        if (
            batch.catalog_version == NORMALIZATION_VERSION
            and record.normalized_data is not None
        ):
            state["cached_rows"] += 1
        if record.idpel != fields["idpel"]:
            record.idpel = fields["idpel"]
        period, text = observation_period(fields.get("tglbaca"))
        values.append((fields["idpel"], record.id, f"{period.isoformat()}|{text}"))
    known = {
        row.idpel: row
        for row in db.query(MasterPreparationIdentity)
        .filter(
            MasterPreparationIdentity.preparation_id == prepared.id,
            MasterPreparationIdentity.idpel.in_({value[0] for value in values}),
        )
        .all()
    }
    for idpel, source_id, period_key in values:
        identity = known.get(idpel)
        if identity is None:
            identity = MasterPreparationIdentity(
                preparation_id=prepared.id, idpel=idpel, base_period="", dil_period=""
            )
            db.add(identity)
            known[idpel] = identity
            state["unique_rows"] += 1
        prefix = "dil" if item["kind"] == "dil" else "base"
        if period_key >= getattr(identity, prefix + "_period"):
            setattr(identity, prefix + "_period", period_key)
            setattr(identity, prefix + "_source_id", source_id)
    if records:
        state["last_source_id"] = records[-1].id
        state["source_rows"] += len(records)
        state["file_rows"] += len(records)
    if len(records) < limit:
        state["file_index"] += 1
        state["last_source_id"] = 0
        state["file_rows"] = 0
        if state["file_index"] == len(prepared.sources):
            state["phase"] = "reserving"
    db.flush()
    return len(records)


def reserve_pdpj_chunk(
    db: Session, prepared: MasterPreparation, state: dict[str, Any], limit: int
) -> int:
    """Reserve approved and pending identities using indexed, resumable reads."""
    review = db.get(PdpjReview, prepared.pdpj_review_id)
    assert review is not None
    if not state["reserving_pending"]:
        records = (
            db.query(PdpjRow.id, PdpjRow.current_fields["idpel"].as_string())
            .filter(
                PdpjRow.review_id == review.id, PdpjRow.id > state["last_review_row_id"]
            )
            .order_by(PdpjRow.id)
            .limit(limit)
            .all()
        )
        if records:
            state["last_review_row_id"] = records[-1][0]
        if len(records) < limit:
            state["reserving_pending"] = True
    elif state["pending_after"] is not None:
        records = (
            db.query(SourceRecord.id, SourceRecord.idpel)
            .filter(
                SourceRecord.batch_id == review.batch_id,
                SourceRecord.id > state["last_pending_source_id"],
            )
            .order_by(SourceRecord.id)
            .limit(limit)
            .all()
        )
        if records:
            state["last_pending_source_id"] = records[-1][0]
        if len(records) < limit:
            state["phase"] = "materializing"
    else:
        records = []
        state["phase"] = "materializing"
    wanted = {idpel for _, idpel in records if idpel}
    existing = {
        idpel
        for (idpel,) in db.query(MasterPreparationExcluded.idpel)
        .filter(
            MasterPreparationExcluded.preparation_id == prepared.id,
            MasterPreparationExcluded.idpel.in_(wanted),
        )
        .all()
    }
    if wanted - existing:
        db.execute(
            insert(MasterPreparationExcluded),
            [
                {"preparation_id": prepared.id, "idpel": value}
                for value in wanted - existing
            ],
        )
    state["pdpj_rows"] += len(records)
    return len(records)


def materialize_chunk(
    db: Session, prepared: MasterPreparation, state: dict[str, Any], limit: int
) -> int:
    """Write a bounded combined master and eligible snapshot, without copying history."""
    identities = (
        db.query(MasterPreparationIdentity)
        .filter(
            MasterPreparationIdentity.preparation_id == prepared.id,
            MasterPreparationIdentity.id > state["last_identity_id"],
        )
        .order_by(MasterPreparationIdentity.id)
        .limit(limit)
        .all()
    )
    wanted = {
        source_id
        for item in identities
        for source_id in (item.base_source_id, item.dil_source_id)
        if source_id is not None
    }
    records = {
        row.id: row
        for row in db.query(SourceRecord)
        .options(
            load_only(
                SourceRecord.id,
                SourceRecord.batch_id,
                SourceRecord.normalized_data,
                SourceRecord.is_valid,
                SourceRecord.validation_errors,
            )
        )
        .filter(SourceRecord.id.in_(wanted))
        .all()
    }
    batches = {item["id"]: db.get(UploadBatch, item["id"]) for item in prepared.sources}
    excluded = {
        value
        for (value,) in db.query(MasterPreparationExcluded.idpel)
        .filter(
            MasterPreparationExcluded.preparation_id == prepared.id,
            MasterPreparationExcluded.idpel.in_([item.idpel for item in identities]),
        )
        .all()
    }
    pending = []
    for offset, item in enumerate(identities):
        selected_source_id = item.base_source_id or item.dil_source_id
        assert selected_source_id is not None
        original = records[selected_source_id]
        batch = batches[original.batch_id]
        assert batch is not None
        fields = cached_fields(original, batch)
        if fields is None:
            raise ValueError("Observasi master berubah saat persiapan")
        fields.update(
            source_batch_id=batch.id,
            source_record_id=original.id,
            source_dataset_type=batch.dataset_type.value,
        )
        if item.base_source_id is not None:
            fields["jenis_pel"] = batch.dataset_type.value.upper()
        if item.base_source_id is not None and item.dil_source_id is not None:
            dil_record = records[item.dil_source_id]
            dil_batch = batches[dil_record.batch_id]
            assert dil_batch is not None
            dil = cached_fields(dil_record, dil_batch)
            assert dil is not None
            for key, value in dil.items():
                if key not in {
                    "lat",
                    "lon",
                    "source_batch_id",
                    "source_record_id",
                    "source_dataset_type",
                    "validation_errors",
                } and fields.get(key) in (None, "", "-"):
                    fields[key] = value
            if (
                (fields.get("lat") is None or fields.get("lon") is None)
                and dil.get("lat") is not None
                and dil.get("lon") is not None
            ):
                fields["lat"], fields["lon"] = dil["lat"], dil["lon"]
        data = {
            **fields,
            "latitude": fields.get("lat"),
            "longitude": fields.get("lon"),
            "koordinat_x": fields.get("lon"),
            "koordinat_y": fields.get("lat"),
            "source_observation_batches": [source["id"] for source in prepared.sources],
        }
        pending.append(
            {
                "batch_id": prepared.master_batch_id,
                "idpel": item.idpel,
                "row_number": state["materialized_rows"] + offset + 2,
                "data": data,
                "normalized_data": fields,
                "is_valid": True,
            }
        )
    if pending:
        source_ids = {
            idpel: row_id
            for row_id, idpel in db.execute(
                insert(SourceRecord).returning(SourceRecord.id, SourceRecord.idpel),
                pending,
            )
        }
        eligible = [
            {
                "snapshot_id": prepared.snapshot_id,
                "source_record_id": source_ids[row["idpel"]],
                "idpel": row["idpel"],
                "nama": row["data"].get("nama"),
                "latitude": row["data"].get("lat"),
                "longitude": row["data"].get("lon"),
                "tarif": row["data"].get("tarif"),
                "daya": row["data"].get("daya"),
                "jenis_layanan": row["data"].get("jenis_pel") or "TIDAK_DIKETAHUI",
            }
            for row in pending
            if row["idpel"] not in excluded
        ]
        if eligible:
            db.execute(insert(MasterSisaRecord), eligible)
        state["eligible_rows"] += len(eligible)
        state["excluded_rows"] += len(pending) - len(eligible)
        state["materialized_rows"] += len(pending)
        state["last_identity_id"] = identities[-1].id
    if len(identities) < limit:
        if state["materialized_rows"] != state["unique_rows"]:
            raise ValueError("Jumlah master tersimpan tidak sesuai checkpoint")
        snapshot = db.get(MasterSnapshot, prepared.snapshot_id)
        master = db.get(UploadBatch, prepared.master_batch_id)
        assert snapshot is not None and master is not None
        snapshot.ready = True
        master.status = BatchStatus.COMPLETED
        master.total_rows = master.valid_rows = state["unique_rows"]
        state["phase"] = "ready"
    return len(identities)


def preparation_info(
    prepared: MasterPreparation, reused: bool = False
) -> dict[str, Any]:
    state = prepared.processing
    reading = state["phase"] == "reading"
    total = (
        state["source_total"]
        + state["pdpj_total"]
        + (state["source_total"] if reading else state["unique_rows"])
    )
    return {
        **state,
        "id": prepared.id,
        "reused": reused,
        "work_total": total,
        "work_done": state["source_rows"]
        + state["pdpj_rows"]
        + state["materialized_rows"],
        "current_file": prepared.sources[state["file_index"]]["filename"]
        if state["file_index"] < len(prepared.sources)
        else None,
    }


def advance_preparation(
    db: Session, process: ReconciliationProcess, previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Save at most a fixed number of source/exclusion/materialization rows per call."""
    if process.master_snapshot_id is not None:
        snapshot = db.get(MasterSnapshot, process.master_snapshot_id)
        if snapshot is not None and snapshot.ready:
            saved_preparation = (
                db.query(MasterPreparation).filter_by(snapshot_id=snapshot.id).first()
            )
            return (
                preparation_info(saved_preparation, True)
                if saved_preparation
                else {"phase": "ready", "reused": True, "work_total": 0, "work_done": 0}
            )
    prepared = get_preparation(db, process)
    reused = prepared.processing["phase"] == "ready" and (
        not previous or previous.get("id") != prepared.id
    )
    state = dict(prepared.processing)
    remaining = PREPARATION_CHUNK_ROWS
    handlers = {
        "reading": read_source_chunk,
        "reserving": reserve_pdpj_chunk,
        "materializing": materialize_chunk,
    }
    while state["phase"] != "ready" and remaining > 0:
        worked = handlers[state["phase"]](
            db, prepared, state, min(READ_BLOCK_ROWS, remaining)
        )
        remaining -= max(1, worked)
    prepared.processing = state
    if state["phase"] == "ready":
        process.master_snapshot_id = prepared.snapshot_id
    db.flush()
    return preparation_info(prepared, reused)
