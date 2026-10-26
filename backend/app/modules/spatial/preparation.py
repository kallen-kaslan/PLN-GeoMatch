"""Create immutable eligible master snapshots, including incomplete identities."""

from typing import Any

from sqlalchemy.orm import Session

from app.models.master_sisa import MasterSisaRecord, MasterSnapshot
from app.models.pdpj import PdpjRow
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.pdpj.service import completed_review
from app.modules.upload.normalization import extract_standard_fields


def process_master_sisa_exclusion(
    db: Session,
    master_batch_id: int,
    pdpj_batch_id: int | None = None,
    *,
    commit: bool = True,
    pdpj_review_id: int | None = None,
) -> dict[str, Any]:
    """Publish a new snapshot; never delete or overwrite another snapshot."""
    master = db.get(UploadBatch, master_batch_id)
    if (
        master is None
        or master.dataset_type != DatasetType.MASTER
        or master.status != BatchStatus.COMPLETED
    ):
        raise ValueError("Batch master tidak ditemukan atau belum siap")
    excluded: set[str] = set()
    if pdpj_batch_id is not None:
        pdpj = db.get(UploadBatch, pdpj_batch_id)
        if (
            pdpj is None
            or pdpj.dataset_type != DatasetType.PDPJ
            or pdpj.status != BatchStatus.COMPLETED
        ):
            raise ValueError("Batch PDPJ tidak ditemukan atau belum siap")
        if pdpj_review_id is not None:
            review = completed_review(db, pdpj_batch_id, pdpj_review_id)
            # Exceptions waive completeness, but their known PDPJ identities must
            # still be reserved so correction candidates cannot reuse them.
            excluded.update(
                idpel
                for (idpel,) in db.query(PdpjRow.current_fields["idpel"].as_string())
                .filter(PdpjRow.review_id == review.id)
                .yield_per(400)
                if idpel
            )
        for record in (
            []
            if pdpj_review_id is not None
            else (db.query(SourceRecord).filter(SourceRecord.batch_id == pdpj.id).all())
        ):
            fields = extract_standard_fields(record.data or {}, pdpj.column_mapping)
            verified = (fields["verif"] or "").lower() not in {
                "0",
                "false",
                "belum",
                "unverified",
            }
            if (
                record.is_valid
                and fields["idpel"]
                and not fields["validation_errors"]
                and verified
            ):
                excluded.add(fields["idpel"])

    snapshot = MasterSnapshot(master_batch_id=master.id, pdpj_batch_id=pdpj_batch_id)
    db.add(snapshot)
    db.flush()
    records = db.query(SourceRecord).filter(SourceRecord.batch_id == master.id).all()
    total_excluded = total_sisa = incomplete = 0
    for record in records:
        fields = extract_standard_fields(record.data or {}, master.column_mapping)
        if not record.is_valid or fields["validation_errors"]:
            continue
        if fields["idpel"] in excluded:
            total_excluded += 1
            continue
        if fields["lat"] is None or fields["lon"] is None:
            incomplete += 1
        db.add(
            MasterSisaRecord(
                snapshot_id=snapshot.id,
                source_record_id=record.id,
                idpel=fields["idpel"] or f"UNASSIGNED-{record.id}",
                nama=fields["nama"],
                latitude=fields["lat"],
                longitude=fields["lon"],
                tarif=fields["tarif"],
                daya=fields["daya"],
                jenis_layanan=fields["jenis_pel"] or "TIDAK_DIKETAHUI",
            )
        )
        total_sisa += 1
    if commit:
        db.commit()
    else:
        db.flush()
    return {
        "status": "success",
        "master_snapshot_id": snapshot.id,
        "total_master": len(records),
        "total_excluded_by_pdpj": total_excluded,
        "total_master_sisa": total_sisa,
        "incomplete_coordinates": incomplete,
    }


def resolve_master_snapshot(
    db: Session, snapshot_id: int | None = None
) -> MasterSnapshot:
    """Resolve a new process default once, before dispatching its job."""
    if snapshot_id is not None:
        snapshot = db.get(MasterSnapshot, snapshot_id)
    else:
        snapshot = db.query(MasterSnapshot).order_by(MasterSnapshot.id.desc()).first()
    if snapshot is None:
        raise ValueError(
            "Master Sisa belum disiapkan; bentuk master dan siapkan snapshot terlebih dahulu"
        )
    return snapshot
