"""Report new PDPJ conflicts without rewriting pinned search results or decisions."""

from typing import Any

from sqlalchemy.orm import Session

from app.models.correction_decision import CorrectionDecision
from app.models.pdpj import PdpjReview, PdpjRow
from app.models.upload import SourceRecord, UploadBatch
from app.modules.corrections.service import reference_tokens
from app.modules.pdpj.service import completed_review, pending_pdpj_records
from app.modules.upload.normalization import (
    extract_standard_fields,
    with_reference_fields,
)


def reserved_keys(
    db: Session, review: PdpjReview
) -> tuple[set[str], set[tuple[str, str]]]:
    """Include pending raw evidence so already reserved values are not new findings."""
    identities: set[str] = set()
    references: set[tuple[str, str]] = set()
    batch = db.get(UploadBatch, review.batch_id)
    assert batch is not None

    def include(fields: dict[str, Any], raw: dict[str, Any]) -> None:
        if fields.get("idpel"):
            identities.add(fields["idpel"])
        for kind, values in reference_tokens(fields, raw, batch.column_mapping).items():
            references.update((kind, value) for value in values)

    for row, source in (
        db.query(PdpjRow, SourceRecord)
        .join(SourceRecord, SourceRecord.id == PdpjRow.source_record_id)
        .filter(PdpjRow.review_id == review.id)
        .yield_per(400)
    ):
        raw = source.data or {}
        include(
            with_reference_fields(row.current_fields, raw, batch.column_mapping), raw
        )
    for source in pending_pdpj_records(db, review):
        include(
            extract_standard_fields(source.data or {}, batch.column_mapping),
            source.data or {},
        )
    return identities, references


def pdpj_update_info(
    db: Session, process_id: int, review_id: int
) -> dict[str, Any] | None:
    """Flag active choices affected by a newer approved version; retain their history."""
    original = db.get(PdpjReview, review_id)
    assert original is not None
    try:
        latest = completed_review(db, original.batch_id)
    except ValueError:
        return None
    if latest.id == original.id:
        return None
    conflicts: list[dict[str, Any]] = []
    events = db.query(CorrectionDecision).filter(
        CorrectionDecision.process_id == process_id
    )
    if events.first() is not None:
        old_ids, old_refs = reserved_keys(db, original)
        new_ids, new_refs = reserved_keys(db, latest)
        new_ids -= old_ids
        new_refs -= old_refs
        seen: set[int] = set()
        for event in events.order_by(
            CorrectionDecision.target_record_id, CorrectionDecision.revision.desc()
        ).yield_per(400):
            if event.target_record_id in seen:
                continue
            seen.add(event.target_record_id)
            if event.candidate_id is None:
                continue
            codes: set[str] = set()
            for fields in (event.target_fields, event.candidate.get("fields", {})):
                if fields.get("idpel") in new_ids:
                    codes.add("idpel_sama_pdpj")
                for kind, values in reference_tokens(fields, {}, None).items():
                    if any((kind, value) in new_refs for value in values):
                        codes.add(f"{kind}_sama_pdpj")
            if codes:
                conflicts.append(
                    {"record_id": event.target_record_id, "codes": sorted(codes)}
                )
    return {
        "review_id": latest.id,
        "publication": latest.publication,
        "conflicts": conflicts,
    }
