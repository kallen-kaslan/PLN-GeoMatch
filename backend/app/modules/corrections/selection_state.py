"""Read current choices across generations without loading their observation payloads."""

from app.models.correction_decision import CorrectionDecision
from sqlalchemy import and_, func
from sqlalchemy.orm import Session


def current_choices(db: Session, process_id: int):
    revisions = (
        db.query(
            CorrectionDecision.target_record_id.label("target"),
            func.max(CorrectionDecision.revision).label("revision"),
        )
        .filter(CorrectionDecision.process_id == process_id)
        .group_by(CorrectionDecision.target_record_id)
        .subquery()
    )
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
