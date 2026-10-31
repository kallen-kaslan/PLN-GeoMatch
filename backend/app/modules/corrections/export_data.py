"""Project saved snapshots into the requested correction spreadsheet columns."""

from typing import Any

from app.models.upload import SourceRecord, UploadBatch
from app.modules.upload.normalization import raw_fields


def text(value: Any) -> str:
    return "" if value is None else str(value)


def coordinate_sources(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Attribute coordinates only to saved observations containing the same pair."""
    fields = candidate.get("fields", {})
    if fields.get("lat") is None or fields.get("lon") is None:
        return []
    matches = [
        item
        for item in candidate.get("observations", [])
        if item.get("fields", {}).get("lat") == fields.get("lat")
        and item.get("fields", {}).get("lon") == fields.get("lon")
    ]
    primary = [
        item
        for item in matches
        if item.get("record_id") == fields.get("source_record_id")
        and item.get("record_id") is not None
    ]
    return primary or matches


def source_label(filename: Any, sheet: Any) -> str:
    return f"{text(filename)} ({sheet})" if sheet else text(filename)


def target_columns(
    source: SourceRecord, batch: UploadBatch, fields: dict[str, Any]
) -> list[Any]:
    raw = raw_fields(source.data or {}, batch.column_mapping)
    return [
        fields.get("agenda_ref") or raw.get("agenda_ref"),
        text(fields.get("idpel")),
        text(fields.get("verif") if "verif" in fields else raw.get("verif")),
        fields.get("jenis_pel"),
        text(fields.get("lat")),
        text(fields.get("lon")),
        source_label(batch.filename, batch.source_sheet),
        source.row_number,
    ]


def result_columns(
    source: SourceRecord,
    batch: UploadBatch,
    target: dict[str, Any],
    candidate: dict[str, Any],
) -> list[Any]:
    values = target_columns(source, batch, target)
    fields = candidate.get("fields", {})
    values[1] = text(fields.get("idpel"))
    values[3] = fields.get("jenis_pel") or target.get("jenis_pel")
    observations = coordinate_sources(candidate)
    values[6] = "\n".join(
        source_label(item.get("filename"), item.get("source_sheet"))
        for item in observations
    )
    values[7] = "\n".join(text(item.get("row_number")) for item in observations)
    return [*values, text(fields.get("lon")), text(fields.get("lat"))]
