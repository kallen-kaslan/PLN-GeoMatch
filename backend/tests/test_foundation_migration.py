"""Exercise the actual Alembic chain with legacy records and startup compatibility."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.database import Base
from app.schema_compatibility import upgrade_foundations


@pytest.mark.parametrize("foreign_keys", [False, True])
def test_migration_preserves_legacy_decisions_and_is_idempotent(
    foreign_keys: bool,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "19218c221efc")
        connection.execute(
            text(
                "INSERT INTO reconciliation_processes (id, process_name, matching_status, review_status, "
                "radius_meters, total_targets, matched_targets) "
                "VALUES (1, 'legacy', 'COMPLETED', 'IN_PROGRESS', 75, 1, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO match_candidates (id, process_id, target_ref, target_lat, target_lon, "
                "candidate_idpel, candidate_lat, candidate_lon, distance_meters, is_accepted) "
                "VALUES (1, 1, 'T1', -6.2, 106.8, '001234567890', -6.2, 106.8, 0, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO master_sisa_records (id, idpel, latitude, longitude) "
                "VALUES (1, '001234567890', -6.2, 106.8)"
            )
        )
        connection.commit()
        if foreign_keys:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            connection.commit()
        command.upgrade(config, "head")
        connection.commit()
        upgrade_foundations(connection)
        connection.commit()
        row = connection.execute(
            text("SELECT is_accepted, generation FROM match_candidates WHERE id=1")
        ).one()
        assert tuple(row) == (1, 1)
        assert (
            connection.execute(text("SELECT COUNT(*) FROM matching_runs")).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM master_snapshots")
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text(
                    "SELECT master_snapshot_id FROM reconciliation_processes WHERE id=1"
                )
            ).scalar_one()
            is None
        )
        assert (
            connection.execute(
                text(
                    "SELECT current_generation FROM reconciliation_processes WHERE id=1"
                )
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT snapshot_id FROM master_sisa_records WHERE id=1")
            ).scalar_one()
            is not None
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        connection.execute(
            text(
                "INSERT INTO master_sisa_records (idpel, latitude, longitude) VALUES ('0013', NULL, NULL)"
            )
        )
        connection.commit()
        assert all(
            column["nullable"]
            for column in inspect(connection).get_columns("master_sisa_records")
            if column["name"] in {"latitude", "longitude"}
        )
    engine.dispose()


def test_startup_upgrade_accepts_fresh_metadata_with_foreign_keys() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(connection)
        upgrade_foundations(connection)
        upgrade_foundations(connection)
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def test_existing_matching_runs_gain_nullable_failure_code_without_losing_history() -> (
    None
):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
        connection.exec_driver_sql("ALTER TABLE matching_runs DROP COLUMN failure_code")
        connection.exec_driver_sql(
            "INSERT INTO reconciliation_processes (id, process_name, current_generation) "
            "VALUES (1, 'existing', 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO matching_runs (id, process_id, generation, status, radius_meters, "
            "total_targets, matched_targets, created_at) "
            "VALUES (1, 1, 1, 'FAILED', 30, 0, 0, CURRENT_TIMESTAMP)"
        )
        upgrade_foundations(connection)
        upgrade_foundations(connection)
        assert tuple(
            connection.exec_driver_sql(
                "SELECT id, status, failure_code FROM matching_runs"
            ).one()
        ) == (1, "FAILED", None)
    engine.dispose()
