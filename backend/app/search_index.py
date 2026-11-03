"""Disposable substring indexes; original predicates remain the source of truth."""

import logging
import threading
import time
from typing import Any
from weakref import WeakKeyDictionary

from sqlalchemy import false, func, literal_column, or_, select, table, true
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
CHUNK_ROWS = 1000
INDEX_VERSION = "v1"
_lock = threading.RLock()
_initialized: WeakKeyDictionary[Engine, set[str]] = WeakKeyDictionary()
_working: WeakKeyDictionary[Engine, set[str]] = WeakKeyDictionary()
_unsupported: WeakKeyDictionary[Engine, bool] = WeakKeyDictionary()

SOURCE_KEYS = (
    "idpel", "nama", "kode_dil", "kode_dlpd", "kddk", "kode_gardu",
    "target_ref", "nomor_meter_kwh", "nomor_meter_prepaid", "meter_ref",
    "agenda_ref", "survey_ref",
)
PROFILES = {
    "source": ("source_records", "id", ("idpel",), "normalized_data", SOURCE_KEYS),
    "pdpj": ("pdpj_rows", "id", (), "current_fields", ("idpel", "nama", "target_ref", "meter_ref", "nomor_meter_kwh", "nomor_meter_prepaid")),
    "target": ("correction_targets", "id", (), "fields", ("idpel", "nama", "meter_ref", "target_ref")),
    "decision": ("correction_decisions", "id", ("actor",), "candidate", ("fields.idpel", "fields.nama")),
}


def _name(kind: str) -> str:
    return f"quick_search_{INDEX_VERSION}_{kind}"


def _eligible(kind: str, prefix: str = "") -> str:
    if kind != "source":
        return "1"
    # Generated combined-master snapshots and raw PDPJ rows are not searched by
    # these source-list endpoints. PDPJ has its own current-fields index.
    return (
        f"{prefix}batch_id IN (SELECT id FROM upload_batches WHERE dataset_type IN "
        "('PASCABAYAR','PRABAYAR','DIL','IDPEL_KOSONG','IDPEL_TIDAK_KETEMU'))"
    )


def _text(kind: str, prefix: str = "") -> str:
    _, _, columns, document, keys = PROFILES[kind]
    values = [prefix + column for column in columns]
    values += [f"json_extract({prefix}{document}, '$.{key}')" for key in keys]
    return " || char(31) || ".join(
        f"coalesce(cast({value} as text), '')" for value in values
    )


def _engine(db: Session) -> Engine | None:
    bind = db.get_bind()
    engine = bind if isinstance(bind, Engine) else bind.engine
    # Test/in-memory databases can share a single connection with an open caller
    # transaction. Never commit that transaction just to build a derived index.
    if engine.dialect.name != "sqlite" or engine.url.database in {None, "", ":memory:"}:
        return None
    return engine


def _initialize(engine: Engine, kind: str) -> bool:
    with _lock:
        if _unsupported.get(engine):
            return False
        if kind in _initialized.get(engine, set()):
            return True
        source, identity, columns, document, _ = PROFILES[kind]
        name = _name(kind)
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE IF NOT EXISTS quick_search_progress "
                    "(kind TEXT PRIMARY KEY, last_id INTEGER NOT NULL, "
                    "through_id INTEGER NOT NULL, processed INTEGER NOT NULL, ready INTEGER NOT NULL)"
                )
                connection.exec_driver_sql(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS {name} USING "
                    "fts5(search_text, tokenize='trigram', detail=none, columnsize=0)"
                )
                if kind == "source":
                    # Refresh the disposable trigger definition when an older
                    # preparation of the same text index used a wider scope.
                    connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name}_insert")
                    connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name}_update")
                connection.exec_driver_sql(
                    f"CREATE TRIGGER IF NOT EXISTS {name}_insert AFTER INSERT ON {source} BEGIN "
                    f"INSERT OR REPLACE INTO {name}(rowid,search_text) "
                    f"SELECT new.{identity},{_text(kind, 'new.')} WHERE {_eligible(kind, 'new.')}; END"
                )
                connection.exec_driver_sql(
                    f"CREATE TRIGGER IF NOT EXISTS {name}_delete AFTER DELETE ON {source} BEGIN "
                    f"DELETE FROM {name} WHERE rowid=old.{identity}; END"
                )
                changed = ",".join((*columns, document, *(("batch_id",) if kind == "source" else ())))
                connection.exec_driver_sql(
                    f"CREATE TRIGGER IF NOT EXISTS {name}_update AFTER UPDATE OF {changed} ON {source} BEGIN "
                    f"DELETE FROM {name} WHERE rowid=old.{identity}; "
                    f"INSERT OR REPLACE INTO {name}(rowid,search_text) "
                    f"SELECT new.{identity},{_text(kind, 'new.')} WHERE {_eligible(kind, 'new.')}; END"
                )
                connection.exec_driver_sql(
                    "INSERT INTO quick_search_progress "
                    f"SELECT ?,0,coalesce((SELECT max({identity}) FROM {source} WHERE {_eligible(kind)}),0),0,0 "
                    "WHERE NOT EXISTS (SELECT 1 FROM quick_search_progress WHERE kind=?)",
                    (_name(kind), _name(kind)),
                )
        except OperationalError as exc:
            if "no such module" in str(exc.orig) or "no such tokenizer" in str(exc.orig):
                _unsupported[engine] = True
                logger.info("SQLite substring index unavailable; retaining original search")
                return False
            raise
        _initialized.setdefault(engine, set()).add(kind)
        return True


def _chunk(engine: Engine, kind: str) -> bool:
    source, identity, _, _, _ = PROFILES[kind]
    with engine.connect() as connection:
        # Serialize only a bounded cache chunk, including its read and cursor.
        # Inserts/edits/deletes in application transactions update FTS by trigger.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            last, through, ready = connection.exec_driver_sql(
                "SELECT last_id,through_id,ready FROM quick_search_progress WHERE kind=?", (_name(kind),)
            ).one()
            if ready:
                connection.commit()
                return True
            # Walk the integer primary key in order. A batch index can otherwise
            # sort the remaining records again for every preparation chunk.
            identities = connection.exec_driver_sql(
                f"SELECT {identity} FROM {source} NOT INDEXED "
                f"WHERE {identity}>? AND {identity}<=? ORDER BY {identity} LIMIT ?",
                (last, through, CHUNK_ROWS),
            ).scalars().all()
            chunk_end = identities[-1] if identities else through
            rows = connection.exec_driver_sql(
                f"SELECT {identity}, {_text(kind)} FROM {source} NOT INDEXED "
                f"WHERE {identity}>? AND {identity}<=? AND {_eligible(kind)} ORDER BY {identity} LIMIT ?",
                (last, chunk_end, CHUNK_ROWS),
            ).fetchall()
            if rows:
                connection.exec_driver_sql(
                    f"INSERT OR REPLACE INTO {_name(kind)}(rowid,search_text) VALUES(?,?)",
                    [tuple(row) for row in rows],
                )
            last = chunk_end
            ready = len(identities) < CHUNK_ROWS or last >= through
            connection.exec_driver_sql(
                "UPDATE quick_search_progress SET last_id=?, processed=processed+?, ready=? WHERE kind=?",
                (through if ready else last, len(rows), int(ready), _name(kind)),
            )
            connection.commit()
            return ready
        except BaseException:
            connection.rollback()
            raise


def _build(engine: Engine, kind: str) -> None:
    try:
        failures = 0
        while True:
            try:
                if _chunk(engine, kind):
                    return
                failures = 0
                time.sleep(0.02)
            except OperationalError as exc:
                if "locked" not in str(exc.orig).lower() and "busy" not in str(exc.orig).lower():
                    logger.error("Search cache build failed: %s", type(exc.orig).__name__)
                    return
                failures += 1
                if failures >= 5:
                    return  # A later request resumes the durable cursor.
                time.sleep(0.2)
    finally:
        with _lock:
            _working.get(engine, set()).discard(kind)


def prepare_search(db: Session, kinds: tuple[str, ...]) -> dict[str, Any] | None:
    """Return preparation state, without scanning source JSON inside a request."""
    engine = _engine(db)
    if engine is None:
        return None
    processed = 0
    complete = True
    for kind in kinds:
        if not _initialize(engine, kind):
            return None
        with engine.connect() as connection:
            ready, through, count = connection.exec_driver_sql(
                "SELECT ready,through_id,processed FROM quick_search_progress WHERE kind=?", (_name(kind),)
            ).one()
        if not ready and through <= CHUNK_ROWS:
            ready = _chunk(engine, kind)
        if not ready:
            complete = False
            with _lock:
                active = _working.setdefault(engine, set())
                if kind not in active:
                    active.add(kind)
                    threading.Thread(target=_build, args=(engine, kind), daemon=True).start()
        processed += count
    return {"ready": complete, "processed_rows": processed}


def search_candidates(db: Session, columns: tuple[tuple[str, Any], ...], q: str) -> Any:
    """Coarse FTS candidate IDs; callers MUST retain their original predicates.

    LIKE intentionally has no ESCAPE here, allowing SQLite's trigram index.
    Wildcards or cross-field matches may overselect; the original escaped LIKE
    removes them. No user input is interpolated into SQL identifiers or paths.
    """
    engine = _engine(db)
    if engine is None or _unsupported.get(engine):
        return true()
    clauses = []
    for kind, column in columns:
        if kind not in _initialized.get(engine, set()):
            return true()
        with engine.connect() as connection:
            ready = connection.exec_driver_sql(
                "SELECT ready FROM quick_search_progress WHERE kind=?", (_name(kind),)
            ).scalar_one()
        if not ready:
            return true()
        matches = select(literal_column("rowid")).select_from(
            table(_name(kind))
        ).where(literal_column("search_text").like("%" + q.strip() + "%"))
        if "\0" not in q:
            # Keep literal %/_ searches selective even though the coarse LIKE
            # deliberately leaves those characters unescaped for FTS.
            matches = matches.where(
                func.instr(func.lower(literal_column("search_text")), func.lower(q.strip())) > 0
            )
        clauses.append(column.in_(matches))
    return or_(*clauses) if clauses else false()


def pending_search(state: dict[str, Any]) -> dict[str, Any]:
    return {"total": 0, "items": [], "search_index": state}
