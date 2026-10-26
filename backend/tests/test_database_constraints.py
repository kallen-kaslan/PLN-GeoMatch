"""Application SQLite connections must reject orphan records before they persist."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import engine


def test_application_sqlite_connections_enforce_foreign_keys() -> None:
    assert engine.dialect.name == "sqlite"
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        connection.execute(
            text("CREATE TEMP TABLE constraint_parent (id INTEGER PRIMARY KEY)")
        )
        connection.execute(
            text(
                "CREATE TEMP TABLE constraint_child (parent_id INTEGER REFERENCES constraint_parent(id))"
            )
        )
        try:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text("INSERT INTO constraint_child (parent_id) VALUES (999)")
                )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM constraint_child")
                ).scalar_one()
                == 0
            )
        finally:
            connection.execute(text("DROP TABLE constraint_child"))
            connection.execute(text("DROP TABLE constraint_parent"))
            connection.commit()
