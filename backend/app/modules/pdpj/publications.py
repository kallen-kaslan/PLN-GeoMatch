"""Copy approved rows, evidence, and history into immutable correction references."""

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Table, and_, insert, literal, select
from sqlalchemy.orm import Session

from app.models.pdpj import PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow


def publish_saved_rows(
    db: Session, review: PdpjReview, actor: str, total: int
) -> PdpjReview:
    """Publish inside the approval transaction; leave the source checkpoint unchanged."""
    assert review.processing is not None
    version = (
        db.query(PdpjReview).filter(PdpjReview.source_review_id == review.id).count()
        + 1
    )
    published = PdpjReview(
        batch_id=review.batch_id,
        master_batch_ids=list(review.master_batch_ids),
        status="completed",
        completed_by=actor,
        completed_at=datetime.now(UTC).replace(tzinfo=None),
        source_review_id=review.id,
        publication={
            "version": version,
            "row_count": total,
            "total_rows": review.processing["total_rows"],
            "last_source_id": review.processing["last_source_id"],
            "last_row_number": review.processing["last_row_number"],
            "source_revision": review.revision,
            "is_partial": total < review.processing["total_rows"],
        },
    )
    db.add(published)
    db.flush()
    rows = cast(Table, PdpjRow.__table__)
    fields = [
        column.name for column in rows.c if column.name not in {"id", "review_id"}
    ]
    db.execute(
        insert(rows).from_select(
            ["review_id", *fields],
            select(literal(published.id), *(rows.c[name] for name in fields)).where(
                rows.c.review_id == review.id
            ),
            include_defaults=False,
        )
    )
    # Copy evidence with a SQL join, so large snapshots do not load every
    # recommendation or audit entry into application memory.
    original, frozen = rows.alias("original"), rows.alias("frozen")
    for model in (PdpjRecommendation, PdpjChange):
        table = cast(Table, model.__table__)
        fields = [
            column.name for column in table.c if column.name not in {"id", "row_id"}
        ]
        source = table.join(original, table.c.row_id == original.c.id).join(
            frozen,
            and_(
                frozen.c.source_record_id == original.c.source_record_id,
                frozen.c.review_id == published.id,
            ),
        )
        db.execute(
            insert(table).from_select(
                ["row_id", *fields],
                select(frozen.c.id, *(table.c[name] for name in fields))
                .select_from(source)
                .where(original.c.review_id == review.id),
                include_defaults=False,
            )
        )
    return published
