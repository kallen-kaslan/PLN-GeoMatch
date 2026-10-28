"""Read original observations only for master identities used as real candidates."""

from typing import Any

from sqlalchemy.orm import Session, load_only

from app.models.upload import SourceRecord, UploadBatch
from app.modules.spatial.master_preparation import cached_fields


def candidate_observations(
    db: Session, originals: dict[int, dict[str, Any]]
) -> dict[int, list[dict[str, Any]]]:
    """Batch indexed lookups; keep legacy embedded evidence compatible."""
    result = {
        source_id: data.get("source_observations", [])
        for source_id, data in originals.items()
    }
    groups: dict[tuple[int, ...], dict[str, list[int]]] = {}
    for source_id, data in originals.items():
        if "source_observation_batches" in data:
            sources = tuple(data["source_observation_batches"])
            groups.setdefault(sources, {}).setdefault(data["idpel"], []).append(
                source_id
            )
    for batch_ids, identities in groups.items():
        batches = {
            batch.id: batch
            for batch in db.query(UploadBatch)
            .filter(UploadBatch.id.in_(batch_ids))
            .all()
        }
        order = {batch_id: index for index, batch_id in enumerate(batch_ids)}
        rows = (
            db.query(SourceRecord)
            .options(
                load_only(
                    SourceRecord.id,
                    SourceRecord.batch_id,
                    SourceRecord.row_number,
                    SourceRecord.normalized_data,
                    SourceRecord.validation_errors,
                    SourceRecord.is_valid,
                )
            )
            .filter(
                SourceRecord.batch_id.in_(batch_ids),
                SourceRecord.idpel.in_(identities),
                SourceRecord.is_valid.is_(True),
            )
            .order_by(SourceRecord.id)
            .yield_per(400)
        )
        for record in rows:
            batch = batches[record.batch_id]
            fields = cached_fields(record, batch)
            if fields is None:
                continue
            observation = {
                "batch_id": batch.id,
                "record_id": record.id,
                "filename": batch.filename,
                "row_number": record.row_number,
                "source_sheet": batch.source_sheet,
                "dataset_type": batch.dataset_type.value,
                "fields": fields,
            }
            for source_id in identities.get(fields["idpel"], []):
                result[source_id].append(observation)
        for source_ids in identities.values():
            for source_id in source_ids:
                result[source_id].sort(
                    key=lambda item: (order[item["batch_id"]], item["record_id"])
                )
    return result
