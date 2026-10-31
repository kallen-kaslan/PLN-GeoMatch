"""Page source identities through batch indexes before reading JSON row payloads."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, load_only

from app.models.upload import SourceRecord


def load_original_cells(db: Session, identities: list[int]) -> None:
    """Batch-load only selected rows that still need raw-cell extraction."""
    if identities:
        db.query(SourceRecord).options(
            load_only(SourceRecord.id, SourceRecord.data)
        ).filter(SourceRecord.id.in_(identities)).all()


def source_page_ids(
    db: Session,
    query: Query[Any],
    batch_ids: list[int],
    skip: int,
    limit: int,
    *,
    unfiltered: bool,
    known_totals: Mapping[int, int | None] | None = None,
) -> tuple[int, list[int]]:
    """Preserve batch-descending/id-ascending order without sorting every payload."""
    if not batch_ids:
        return 0, []
    counts: dict[int, int] = {}
    if unfiltered:
        # Confirmed imports keep their actual row count. Legacy batches without
        # that count still use the indexed database count below.
        counts = {
            batch_id: number
            for batch_id, number in (known_totals or {}).items()
            if batch_id in batch_ids and number is not None and number > 0
        }
    unknown = set(batch_ids) - counts.keys()
    if unknown:
        counts_query = (
            db.query(SourceRecord).filter(SourceRecord.batch_id.in_(unknown))
            if unfiltered
            else query
        )
        counts.update(
            {
                batch_id: number
                for batch_id, number in counts_query.with_entities(
                    SourceRecord.batch_id, func.count(SourceRecord.id)
                )
                .order_by(None)
                .group_by(SourceRecord.batch_id)
                .all()
            }
        )
    total = sum(counts.values())
    if skip >= total:
        return total, []
    identities: list[int] = []
    for batch_id in sorted(set(batch_ids), reverse=True):
        number = counts.get(batch_id, 0)
        if skip >= number:
            skip -= number
            continue
        selected = db.query(SourceRecord) if unfiltered else query
        identities.extend(
            record_id
            for (record_id,) in selected.with_entities(SourceRecord.id)
            .filter(SourceRecord.batch_id == batch_id)
            .order_by(None)
            .order_by(SourceRecord.id)
            .offset(skip)
            .limit(limit - len(identities))
            .all()
        )
        skip = 0
        if len(identities) == limit:
            break
    return total, identities
