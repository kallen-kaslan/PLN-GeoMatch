"""Read current choices across generations without loading their observation payloads."""

from app.models.correction_decision import CorrectionDecision
from app.models.upload import SourceRecord
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session


def current_choices(db: Session, process_id: int, generation: int | None = None):
    revisions_query = db.query(
        CorrectionDecision.target_record_id.label("target"),
        func.max(CorrectionDecision.revision).label("revision"),
    ).filter(CorrectionDecision.process_id == process_id)
    if generation is not None:
        revisions_query = revisions_query.filter(
            CorrectionDecision.generation <= generation
        )
    revisions = revisions_query.group_by(CorrectionDecision.target_record_id).subquery()
    return (
        db.query(CorrectionDecision)
        .join(
            revisions,
            and_(
                CorrectionDecision.target_record_id == revisions.c.target,
                CorrectionDecision.revision == revisions.c.revision,
            ),
        )
        .filter(CorrectionDecision.process_id == process_id)
    )


def saved_choice_summary(
    db: Session, process_id: int, generation: int, radius: float
) -> dict[str, int | float | None]:
    """Separate saved choices by radius without loading their evidence payloads."""
    active = CorrectionDecision.candidate_id.is_not(None)
    distance = CorrectionDecision.candidate["distance_meters"].as_float()
    row = (
        current_choices(db, process_id, generation)
        .with_entities(
            func.sum(case((active, 1), else_=0)),
            func.sum(case((and_(active, distance.between(0, radius)), 1), else_=0)),
            func.sum(case((and_(active, distance > radius), 1), else_=0)),
            func.sum(case((CorrectionDecision.candidate_id.is_(None), 1), else_=0)),
            func.max(case((and_(active, distance >= 0), distance), else_=None)),
        )
        .one()
    )
    total, within, outside, cancelled = (int(value or 0) for value in row[:4])
    return {
        "radius_meters": radius,
        "active_count": total,
        "within_radius_count": within,
        "outside_radius_count": outside,
        "unknown_distance_count": total - within - outside,
        "cancelled_count": cancelled,
        "max_distance_meters": row[4],
    }


def identity_owners(db: Session, process_id: int) -> dict[str, list[int]]:
    owners: dict[str, list[int]] = {}
    for record, identity in (
        current_choices(db, process_id)
        .filter(CorrectionDecision.candidate_id.is_not(None))
        .with_entities(
            CorrectionDecision.target_record_id,
            CorrectionDecision.candidate["fields"]["idpel"].as_string(),
        )
    ):
        if identity:
            owners.setdefault(identity, []).append(record)
    return owners


def candidate_usage(
    db: Session, process_id: int, identities: list[str]
) -> dict[str, list[dict[str, int]]]:
    if not identities:
        return {}
    identity = CorrectionDecision.candidate["fields"]["idpel"].as_string()
    usage: dict[str, list[dict[str, int]]] = {}
    for value, record, row in (
        current_choices(db, process_id)
        .join(SourceRecord, SourceRecord.id == CorrectionDecision.target_record_id)
        .filter(CorrectionDecision.candidate_id.is_not(None), identity.in_(identities))
        .with_entities(identity, SourceRecord.id, SourceRecord.row_number)
    ):
        usage.setdefault(value, []).append({"record_id": record, "row_number": row})
    return usage
