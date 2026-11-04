"""Read stored review states through a covering index and reuse unchanged counts."""

from collections import OrderedDict
from threading import RLock
from typing import Any
from weakref import WeakKeyDictionary

from app.models.pdpj import (
    PdpjReview,
    PdpjRow,
    pdpj_coordinates_missing,
    pdpj_issue_count,
)
from sqlalchemy import and_, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

_cache: WeakKeyDictionary[Engine, OrderedDict[tuple[Any, ...], dict[str, int]]] = (
    WeakKeyDictionary()
)
_lock = RLock()
MAX_CACHED_REVISIONS = 128


def cache_key(review: PdpjReview) -> tuple[Any, ...]:
    # Creation time prevents a reset/reimport with reused IDs from reading old counts.
    return (
        review.id,
        review.revision,
        review.created_at,
        (review.processing or {}).get("processed_rows"),
        (review.publication or {}).get("row_count"),
    )


def cached_counts(db: Session, review: PdpjReview) -> dict[str, int] | None:
    with _lock:
        entries = _cache.get(db.get_bind().engine)
        key = cache_key(review)
        if entries is not None and key in entries:
            entries.move_to_end(key)
            return dict(entries[key])
    return None


def review_counts(db: Session, review: PdpjReview) -> dict[str, int]:
    cached = cached_counts(db, review)
    if cached is not None:
        return cached
    unresolved = and_(pdpj_issue_count() > 0, PdpjRow.exception.is_(False))
    total, found, not_found, empty, invalid, incomplete, exceptions, pending = (
        db.query(
            func.count(PdpjRow.id),
            *(
                func.count(PdpjRow.id).filter(PdpjRow.existence == value)
                for value in ("found", "not_found", "empty", "invalid")
            ),
            func.count(PdpjRow.id).filter(pdpj_coordinates_missing().is_(True)),
            func.count(PdpjRow.id).filter(PdpjRow.exception.is_(True)),
            func.count(PdpjRow.id).filter(unresolved),
        )
        .filter(PdpjRow.review_id == review.id)
        .one()
    )
    counts = {
        "total_rows": total,
        "found": found,
        "not_found": not_found,
        "empty": empty,
        "invalid": invalid,
        "incomplete_coordinates": incomplete,
        "exceptions": exceptions,
        "unresolved": pending,
        "ready": total - pending - exceptions,
    }
    with _lock:
        entries = _cache.setdefault(db.get_bind().engine, OrderedDict())
        entries[cache_key(review)] = counts
        entries.move_to_end(cache_key(review))
        while len(entries) > MAX_CACHED_REVISIONS:
            entries.popitem(last=False)
    return dict(counts)


def saved_total(db: Session, review: PdpjReview, status: str) -> int | None:
    counts = cached_counts(db, review)
    if counts is not None:
        key = {
            "all": "total_rows",
            "incomplete": "incomplete_coordinates",
            "exception": "exceptions",
        }.get(status, status)
        return counts.get(key)
    if status == "all":
        value = (
            (review.publication or {}).get("row_count")
            if review.source_review_id is not None
            else (review.processing or {}).get("processed_rows")
        )
        if isinstance(value, int) and value >= 0:
            return value
    return None
