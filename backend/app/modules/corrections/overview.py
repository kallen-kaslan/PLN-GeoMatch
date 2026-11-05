"""Read-only category overviews across imports and retained search evidence."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, and_, case, cast, func, or_
from sqlalchemy.orm import Session, load_only, undefer

from app.database import get_db
from app.models.correction import CorrectionCheck, CorrectionTarget
from app.models.correction_decision import CorrectionDecision
from app.models.matching import MatchingRun
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.models.radius_analysis import RadiusAnalysis, RadiusAnalysisRow
from app.modules.upload.normalization import extract_standard_fields

router = APIRouter()
OverviewStatus = Literal[
    "all", "not_processed", "coordinate_issues", "no_candidates",
    "candidates_found", "idpel_in_pdpj",
]


def overview_query(db: Session, *, include_choices: bool = True, kind: DatasetType = DatasetType.IDPEL_KOSONG):
    # Aggregate latest saved runs once, rather than probing history per source row. A new,
    # unfinished search must not hide the previous result or a retained choice.
    latest_outcomes = (
        db.query(
            CorrectionTarget.source_record_id.label("source_id"),
            func.max(CorrectionTarget.run_id).label("run_id"),
        )
        .join(MatchingRun, MatchingRun.id == CorrectionTarget.run_id)
        .join(CorrectionCheck, CorrectionCheck.process_id == MatchingRun.process_id)
        .filter(CorrectionCheck.category == kind.value)
        .group_by(CorrectionTarget.source_record_id)
        .subquery()
    )
    latest_choice = (
        db.query(CorrectionDecision.id)
        .filter(CorrectionDecision.target_record_id == SourceRecord.id)
        .order_by(CorrectionDecision.id.desc())
        .limit(1).correlate(SourceRecord).scalar_subquery()
    )
    def field(key: str):
        return case(
            (CorrectionTarget.id.is_not(None), CorrectionTarget.fields[key].as_string()),
            else_=SourceRecord.normalized_data[key].as_string(),
        )

    coordinates_missing = and_(
        or_(
            CorrectionTarget.id.is_not(None),
            SourceRecord.normalized_data["_normalization_version"].as_integer().is_not(None),
        ),
        or_(field("lat").is_(None), field("lon").is_(None)),
    )
    idpel_in_pdpj = or_(
        and_(CorrectionTarget.search_status == "pdpj_conflict", cast(CorrectionTarget.conflicts, String).contains('"idpel_sama_pdpj"')),
        and_(CorrectionTarget.id.is_(None), RadiusAnalysisRow.issue == "idpel_in_pdpj"),
    ) if kind == DatasetType.IDPEL_TIDAK_KETEMU else False
    status = case(
        (idpel_in_pdpj, "idpel_in_pdpj"),
        (coordinates_missing, "coordinate_issues"),
        (CorrectionTarget.id.is_(None), "not_processed"),
        (and_(CorrectionTarget.search_status == "matched", CorrectionTarget.candidate_count > 0), "candidates_found"),
        (CorrectionTarget.search_status == "no_candidates", "no_candidates"),
        else_="not_processed",
    ).label("overview_status")
    query = (
        db.query(SourceRecord, UploadBatch, CorrectionTarget, MatchingRun, *([CorrectionDecision] if include_choices else []), status)
        .select_from(SourceRecord)
        .options(load_only(
            SourceRecord.id, SourceRecord.batch_id, SourceRecord.row_number,
            SourceRecord.normalized_data,
        ))
        .join(UploadBatch, UploadBatch.id == SourceRecord.batch_id)
        .outerjoin(latest_outcomes, latest_outcomes.c.source_id == SourceRecord.id)
        .outerjoin(CorrectionTarget, and_(
            CorrectionTarget.source_record_id == SourceRecord.id,
            CorrectionTarget.run_id == latest_outcomes.c.run_id,
        ))
        .outerjoin(MatchingRun, MatchingRun.id == CorrectionTarget.run_id)
        .filter(
            SourceRecord.batch_id.in_(
                db.query(UploadBatch.id).filter(
                    UploadBatch.dataset_type == kind,
                    UploadBatch.status == BatchStatus.COMPLETED,
                )
            ),
            UploadBatch.dataset_type == kind,
            UploadBatch.status == BatchStatus.COMPLETED,
        )
    )
    if kind == DatasetType.IDPEL_TIDAK_KETEMU:
        latest_analysis = db.query(RadiusAnalysis.batch_id, func.max(RadiusAnalysis.id).label("analysis_id")).group_by(RadiusAnalysis.batch_id).subquery()
        query = query.outerjoin(latest_analysis, latest_analysis.c.batch_id == SourceRecord.batch_id).outerjoin(
            RadiusAnalysisRow,
            and_(RadiusAnalysisRow.analysis_id == latest_analysis.c.analysis_id, RadiusAnalysisRow.source_record_id == SourceRecord.id),
        )
    if include_choices:
        query = query.outerjoin(CorrectionDecision, CorrectionDecision.id == latest_choice)
    return query, status, field


# Process.tsx writes one manual point with this fixed CSV format. Require the
# format as well as the reserved prefix, so a document named manual-*.csv alone
# is not treated as manual input. No existing batches are rewritten.
def manual_source():
    headers = cast(UploadBatch.source_headers, String)
    return and_(
        UploadBatch.filename.startswith("manual-"),
        UploadBatch.total_rows == 1,
        UploadBatch.source_sheet.is_(None),
        *(headers.contains('"' + key + '"') for key in (
            "IDPEL", "ID_TITIK", "NOAGENDA", "NOMOR_METER",
            "LATITUDEY", "LONGITUDEX", "KETERANGAN",
        )),
    )


def filter_source(query, source: str, batch_id: int | None):
    if source == "manual":
        query = query.filter(manual_source())
    elif source == "document":
        query = query.filter(~func.coalesce(manual_source(), False))
    if batch_id is not None:
        query = query.filter(UploadBatch.id == batch_id)
    return query


def overview_sources(db: Session, kind: DatasetType):
    batches = db.query(UploadBatch).filter(
        UploadBatch.dataset_type == kind,
        UploadBatch.status == BatchStatus.COMPLETED,
        ~func.coalesce(manual_source(), False),
        db.query(SourceRecord.id).filter(SourceRecord.batch_id == UploadBatch.id).exists(),
    ).order_by(UploadBatch.id.desc()).all()
    return [{"id": batch.id, "filename": batch.filename,
             "source_sheet": batch.source_sheet} for batch in batches]


def overview_summary(db: Session, kind: DatasetType) -> dict[str, Any]:
    query, status, _ = overview_query(db, include_choices=False, kind=kind)
    counts = dict(query.with_entities(status, func.count(SourceRecord.id)).group_by(status).all())
    return {"total_rows": sum(counts.values()), "counts": counts}


def overview_records(db: Session, kind: DatasetType, q: str, status: OverviewStatus, skip: int, limit: int, source: str = "all", batch_id: int | None = None) -> dict[str, Any]:
    query, status_column, field = overview_query(db, kind=kind)
    query = filter_source(query, source, batch_id)
    if status != "all":
        query = query.filter(status_column == status)
    if q.strip():
        pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(or_(
            *(field(key).ilike(pattern, escape="\\") for key in (
                "nama", "agenda_ref", "meter_ref", "nomor_meter_kwh", "target_ref",
                *(("idpel",) if kind == DatasetType.IDPEL_TIDAK_KETEMU else ()),
            )),
            CorrectionDecision.candidate["fields"]["idpel"].as_string().ilike(pattern, escape="\\"),
        ))
    if q.strip():
        total = query.count()
    else:
        count_query, count_status, _ = overview_query(db, include_choices=False, kind=kind)
        count_query = filter_source(count_query, source, batch_id)
        if status != "all":
            count_query = count_query.filter(count_status == status)
        total = count_query.with_entities(func.count(SourceRecord.id)).scalar()
    items = []
    page = (
        query.options(undefer(SourceRecord.data)).order_by(SourceRecord.batch_id.desc(), SourceRecord.id).offset(skip).limit(limit).all()
    )
    analyses = dict(db.query(RadiusAnalysis.batch_id, func.max(RadiusAnalysis.id)).filter(
        RadiusAnalysis.batch_id.in_({row[1].id for row in page})
    ).group_by(RadiusAnalysis.batch_id).all()) if page else {}
    for source, batch, outcome, run, choice, row_status in page:
        fields = outcome.fields if outcome else source.normalized_data
        if not fields:
            fields = extract_standard_fields(source.data or {}, batch.column_mapping)
        items.append({
            "id": source.id, "batch_id": source.batch_id,
            "row_number": source.row_number, "filename": batch.filename,
            "object_id": next((value for key, value in (source.data or {}).items()
                if "".join(char for char in key.lower() if char.isalnum()) in ("objectid", "objekid")), None),
            "source_sheet": batch.source_sheet, "fields": fields,
            "status": row_status, "search_status": outcome.search_status if outcome else "not_checked",
            "candidate_count": outcome.candidate_count if outcome else 0,
            "process_id": run.process_id if run else None,
            "analysis_id": analyses.get(batch.id),
            "generation": run.generation if run else None,
            "radius_meters": run.radius_meters if run else None,
            "choice": {
                "idpel": (choice.candidate or {}).get("fields", {}).get("idpel"),
                "process_id": choice.process_id, "generation": choice.generation,
            } if choice and choice.candidate_id is not None else None,
        })
    return {"total": total, "items": items}


@router.get("/idpel_kosong/overview/summary")
def summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    return overview_summary(db, DatasetType.IDPEL_KOSONG)


@router.get("/idpel_kosong/overview/records")
def records(q: str = Query("", max_length=120), status: OverviewStatus = "all", skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), db: Session = Depends(get_db), source: Literal["all", "document", "manual"] = "all", batch_id: int | None = None) -> dict[str, Any]:
    return overview_records(db, DatasetType.IDPEL_KOSONG, q, status, skip, limit, source, batch_id)


@router.get("/idpel_tidak_ketemu/overview/summary")
def not_found_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    return overview_summary(db, DatasetType.IDPEL_TIDAK_KETEMU)


@router.get("/idpel_tidak_ketemu/overview/records")
def not_found_records(q: str = Query("", max_length=120), status: OverviewStatus = "all", skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), db: Session = Depends(get_db), source: Literal["all", "document", "manual"] = "all", batch_id: int | None = None) -> dict[str, Any]:
    return overview_records(db, DatasetType.IDPEL_TIDAK_KETEMU, q, status, skip, limit, source, batch_id)


@router.get("/idpel_kosong/overview/sources")
def empty_sources(db: Session = Depends(get_db)):
    return overview_sources(db, DatasetType.IDPEL_KOSONG)


@router.get("/idpel_tidak_ketemu/overview/sources")
def not_found_sources(db: Session = Depends(get_db)):
    return overview_sources(db, DatasetType.IDPEL_TIDAK_KETEMU)
