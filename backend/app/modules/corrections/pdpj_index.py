"""Reuse compact approved-version keys; hydrate full evidence only for real conflicts."""

import json
from collections import defaultdict
from collections.abc import Hashable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import islice
from threading import RLock
from typing import Any, Generic, TypeVar
from weakref import WeakKeyDictionary

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models.pdpj import PdpjReview, PdpjRow
from app.models.upload import SourceRecord, UploadBatch
from app.modules.corrections.service import reference_tokens
from app.modules.upload.normalization import (
    NORMALIZATION_VERSION,
    extract_standard_fields,
    with_reference_fields,
)
from app.performance import timed

Evidence = dict[str, Any]
Key = TypeVar("Key", bound=Hashable)


@dataclass
class CompactIndex:
    identities: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    references: dict[tuple[str, str], list[int]] = field(
        default_factory=lambda: defaultdict(list)
    )
    coordinates: dict[tuple[float, float], list[int]] = field(
        default_factory=lambda: defaultdict(list)
    )


class EvidenceLookup(Mapping[Key, list[Evidence]], Generic[Key]):
    def __init__(
        self, keys: dict[Key, list[int]], evidence: dict[int, Evidence]
    ) -> None:
        self.keys_index = keys
        self.evidence = evidence

    def __getitem__(self, key: Key) -> list[Evidence]:
        if key not in self.keys_index:
            raise KeyError(key)
        tokens = self.keys_index[key]
        if any(token not in self.evidence for token in tokens):
            raise ValueError("Bukti benturan PDPJ belum termuat lengkap")
        return [self.evidence[token] for token in tokens]

    def __iter__(self) -> Iterator[Key]:
        return iter(self.keys_index)

    def __len__(self) -> int:
        return len(self.keys_index)

    def __contains__(self, key: object) -> bool:
        return key in self.keys_index


@dataclass
class ConflictContext:
    identities: Mapping[str, list[Evidence]]
    references: Mapping[tuple[str, str], list[Evidence]]
    coordinates: dict[tuple[float, float], list[int]]


# Keep at most one compact version per engine, without retaining ORM rows/raw cells.
_cache: WeakKeyDictionary[Engine, tuple[str, CompactIndex]] = WeakKeyDictionary()
_lock = RLock()


def clear_pdpj_indexes() -> None:
    with _lock:
        _cache.clear()


def add_keys(
    index: CompactIndex,
    token: int,
    fields: Evidence,
    raw: Evidence,
    batch: UploadBatch,
    row_number: int | None = None,
) -> None:
    if fields.get("idpel"):
        index.identities[fields["idpel"]].append(token)
    for kind, values in reference_tokens(fields, raw, batch.column_mapping).items():
        for value in values:
            index.references[(kind, value)].append(token)
    if (
        row_number is not None
        and fields.get("lat") is not None
        and fields.get("lon") is not None
    ):
        index.coordinates[(round(fields["lat"], 7), round(fields["lon"], 7))].append(
            row_number
        )


@timed("corrections.build_pdpj_index")
def build_index(db: Session, review: PdpjReview, batch: UploadBatch) -> CompactIndex:
    index = CompactIndex()
    rows = iter(
        db.query(
            PdpjRow.id,
            PdpjRow.source_record_id,
            PdpjRow.row_number,
            PdpjRow.current_fields,
        )
        .filter(PdpjRow.review_id == review.id)
        .order_by(PdpjRow.id)
        .yield_per(400)
    )
    while block := list(islice(rows, 400)):
        legacy = [
            source_id
            for _, source_id, _, current in block
            if not all(
                key in current for key in ("meter_ref", "agenda_ref", "survey_ref")
            )
        ]
        originals = (
            dict(
                db.query(SourceRecord.id, SourceRecord.data)
                .filter(SourceRecord.id.in_(legacy))
                .all()
            )
            if legacy
            else {}
        )
        for row_id, source_id, number, current in block:
            raw = originals.get(source_id) or {}
            fields = with_reference_fields(current, raw, batch.column_mapping)
            add_keys(index, row_id, fields, raw, batch, number)
    if review.source_review_id is not None and review.publication:
        for source_id, number, raw in (
            db.query(SourceRecord.id, SourceRecord.row_number, SourceRecord.data)
            .filter(
                SourceRecord.batch_id == review.batch_id,
                SourceRecord.id > review.publication["last_source_id"],
            )
            .order_by(SourceRecord.id)
            .yield_per(400)
        ):
            fields = extract_standard_fields(raw or {}, batch.column_mapping)
            add_keys(index, -source_id, fields, raw or {}, batch)
    return index


def get_index(db: Session, review: PdpjReview, batch: UploadBatch) -> CompactIndex:
    engine = db.get_bind().engine
    signature = json.dumps(
        [
            NORMALIZATION_VERSION,
            review.id,
            str(review.created_at),
            review.revision,
            review.source_review_id,
            review.publication,
            batch.id,
            str(batch.created_at),
            batch.column_mapping,
            batch.catalog_version,
        ],
        sort_keys=True,
    )
    with _lock:
        cached = _cache.get(engine)
        if cached is not None and cached[0] == signature:
            return cached[1]
        index = build_index(db, review, batch)
        _cache[engine] = (signature, index)
        return index


@timed("corrections.load_chunk_conflicts")
def chunk_context(
    db: Session,
    review: PdpjReview,
    fields: Sequence[Evidence],
    raw_targets: Sequence[Evidence],
    target_batch: UploadBatch,
) -> ConflictContext:
    batch = db.get(UploadBatch, review.batch_id)
    assert batch is not None
    index = get_index(db, review, batch)
    wanted: set[int] = set()
    for target, raw in zip(fields, raw_targets):
        if identity := target.get("idpel"):
            wanted.update(index.identities.get(identity, []))
        for kind, values in reference_tokens(
            target, raw, target_batch.column_mapping
        ).items():
            for value in values:
                wanted.update(index.references.get((kind, value), []))
    evidence: dict[int, Evidence] = {}
    tokens = sorted(wanted)
    for start in range(0, len(tokens), 400):
        group = tokens[start : start + 400]
        approved = [token for token in group if token > 0]
        pending = [-token for token in group if token < 0]
        if approved:
            for row_id, number, current, raw in (
                db.query(
                    PdpjRow.id,
                    PdpjRow.row_number,
                    PdpjRow.current_fields,
                    SourceRecord.data,
                )
                .join(SourceRecord, SourceRecord.id == PdpjRow.source_record_id)
                .filter(PdpjRow.review_id == review.id, PdpjRow.id.in_(approved))
            ):
                evidence[row_id] = {
                    "pdpj_row_id": row_id,
                    "row_number": number,
                    "fields": with_reference_fields(
                        current, raw or {}, batch.column_mapping
                    ),
                }
        if pending:
            for source_id, number, raw in (
                db.query(SourceRecord.id, SourceRecord.row_number, SourceRecord.data)
                .filter(
                    SourceRecord.batch_id == review.batch_id,
                    SourceRecord.id.in_(pending),
                )
                .order_by(SourceRecord.id)
            ):
                evidence[-source_id] = {
                    "pdpj_row_id": None,
                    "row_number": number,
                    "fields": extract_standard_fields(raw or {}, batch.column_mapping),
                    "pending_validation": True,
                }
    if set(evidence) != wanted:
        raise ValueError("Bukti benturan PDPJ tidak sesuai versi tersimpan")
    return ConflictContext(
        EvidenceLookup(index.identities, evidence),
        EvidenceLookup(index.references, evidence),
        index.coordinates,
    )
