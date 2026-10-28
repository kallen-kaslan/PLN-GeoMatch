"""Run structural upgrades once; keep data preparation incremental by batch."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Table, select
from sqlalchemy.engine import Connection

from app.models.schema_state import SchemaState
from app.performance import logger, timed


@timed("startup.schema_stage")
def apply_once(
    connection: Connection,
    stage: str,
    version: str,
    operation: Callable[[Connection], None],
) -> None:
    states = cast(Table, SchemaState.__table__)
    current = connection.execute(
        select(states.c.version).where(states.c.stage == stage)
    ).scalar_one_or_none()
    if current == version:
        return
    logger.info("startup schema_step=%s status=running", stage)
    operation(connection)
    values = {"version": version, "applied_at": datetime.now(UTC).replace(tzinfo=None)}
    if current is None:
        connection.execute(states.insert().values(stage=stage, **values))
    else:
        connection.execute(
            states.update().where(states.c.stage == stage).values(**values)
        )
    logger.info("startup schema_step=%s status=completed", stage)


def prepare_database(connection: Connection) -> None:
    from app.coordinate_schema import repair_xy_coordinates
    from app.correction_map_schema import upgrade_correction_map
    from app.correction_progress_schema import upgrade_correction_progress
    from app.correction_schema import upgrade_corrections
    from app.master_preparation_schema import upgrade_master_preparation
    from app.master_schema import upgrade_master_catalog
    from app.pdpj_progress_schema import upgrade_pdpj_progress
    from app.pdpj_publication_schema import upgrade_pdpj_publications
    from app.pdpj_schema import upgrade_pdpj_validation
    from app.performance_schema import upgrade_performance
    from app.schema_compatibility import upgrade_foundations
    from app.upload_file_schema import upgrade_upload_files

    cast(Table, SchemaState.__table__).create(connection, checkfirst=True)
    apply_once(
        connection, "foundations", "e5fa92c30b71-indexed-fk-v1", upgrade_foundations
    )
    # The batch indexes are needed before any legacy data is inspected.
    apply_once(connection, "performance", "e5fa92c30b71", upgrade_performance)
    upgrade_master_catalog(connection)
    apply_once(connection, "pdpj", "f6ac81d43e20", upgrade_pdpj_validation)
    apply_once(connection, "pdpj_progress", "a91d72f04c63", upgrade_pdpj_progress)
    apply_once(
        connection, "pdpj_publications", "b02c83e15d74", upgrade_pdpj_publications
    )
    apply_once(connection, "corrections", "f21a85db4e09", upgrade_corrections)
    apply_once(
        connection, "correction_progress", "c13d94f26e85", upgrade_correction_progress
    )
    apply_once(connection, "correction_map", "a4b19c7e6201", upgrade_correction_map)
    apply_once(
        connection, "master_preparation", "d24ea5037f96", upgrade_master_preparation
    )
    apply_once(connection, "upload_files", "c8d72fe610ab", upgrade_upload_files)
    repair_xy_coordinates(connection)
