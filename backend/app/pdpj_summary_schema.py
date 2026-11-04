"""Make saved PDPJ summary reads independent of the size of customer JSON fields."""

from app.models.pdpj import PDPJ_SUMMARY_INDEX, PdpjRow
from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def upgrade_pdpj_summary(connection: Connection) -> None:
    existing = (
        {row[1] for row in connection.exec_driver_sql("PRAGMA index_list('pdpj_rows')")}
        if connection.dialect.name == "sqlite"
        else {index["name"] for index in inspect(connection).get_indexes("pdpj_rows")}
    )
    if PDPJ_SUMMARY_INDEX not in existing:
        next(
            index
            for index in PdpjRow.__table__.indexes
            if index.name == PDPJ_SUMMARY_INDEX
        ).create(connection)
