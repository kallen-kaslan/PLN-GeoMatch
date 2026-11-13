"""Read current choices across generations without loading their observation payloads."""

from app.models.correction_decision import CorrectionDecision
from app.models.upload import SourceRecord
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
