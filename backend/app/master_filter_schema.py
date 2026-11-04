"""Index master conditions without changing original or normalized source values."""

from app.models.upload import MASTER_FILTER_INDEX_NAMES, SourceRecord
from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def upgrade_master_filters(connection: Connection) -> None:
    # SQLite's generic inspector omits expression indexes; use its index list so
    # new databases and repeated startup upgrades do not try to create them twice.
    existing = (
        {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA index_list('source_records')")
        }
        if connection.dialect.name == "sqlite"
        else {
            index["name"] for index in inspect(connection).get_indexes("source_records")
        }
    )
    for index in sorted(
        SourceRecord.__table__.indexes, key=lambda item: item.name or ""
    ):
        if index.name in MASTER_FILTER_INDEX_NAMES and index.name not in existing:
            index.create(connection)
