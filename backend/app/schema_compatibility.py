"""Idempotent, data-preserving foundation migration for existing installations."""

from typing import cast

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Connection


def upgrade_foundations(connection: Connection) -> None:
    """Apply the same schema changes during Alembic and legacy app startup."""
    from app.models.master_sisa import MasterSnapshot
    from app.models.matching import MatchingRun

    if connection.dialect.name == "sqlite":
        # Batch recreation temporarily replaces referenced parent tables. Check
        # their foreign keys after all original primary keys have been restored.
        driver_connection = connection.connection.driver_connection
        assert driver_connection is not None
        if not driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
        connection.exec_driver_sql("PRAGMA defer_foreign_keys=ON")
    op = Operations(MigrationContext.configure(connection))
    cast(sa.Table, MasterSnapshot.__table__).create(connection, checkfirst=True)
    additions = {
        "upload_batches": [sa.Column("source_headers", sa.JSON(), nullable=True)],
        "source_records": [
            sa.Column(
                "is_valid", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("validation_errors", sa.JSON(), nullable=True),
        ],
        "reconciliation_processes": [
            sa.Column("master_snapshot_id", sa.Integer(), nullable=True),
            sa.Column("target_batch_id", sa.Integer(), nullable=True),
            sa.Column(
                "current_generation", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("source_batches", sa.JSON(), nullable=True),
        ],
        "match_candidates": [
            sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("target_record_id", sa.Integer(), nullable=True),
        ],
    }
    for table, new_columns in additions.items():
        existing_names = {
            column["name"] for column in sa.inspect(connection).get_columns(table)
        }
        for column in new_columns:
            if column.name not in existing_names:
                op.add_column(table, column)

    reflected_columns = {
        column["name"]: column
        for column in sa.inspect(connection).get_columns("master_sisa_records")
    }
    missing = [
        column
        for column in (
            sa.Column("snapshot_id", sa.Integer(), nullable=True),
            sa.Column("source_record_id", sa.Integer(), nullable=True),
            sa.Column(
                "jenis_layanan", sa.String(), server_default="PASCABAYAR", nullable=True
            ),
        )
        if column.name not in reflected_columns
    ]
    if (
        missing
        or not reflected_columns["latitude"]["nullable"]
        or not reflected_columns["longitude"]["nullable"]
    ):
        with op.batch_alter_table("master_sisa_records") as batch:
            for column in missing:
                batch.add_column(column)
            for field in ("latitude", "longitude"):
                if not reflected_columns[field]["nullable"]:
                    batch.alter_column(field, existing_type=sa.Float(), nullable=True)

    # Name foreign keys explicitly so SQLite's batch migration can recreate them.
    for table, keys in {
        "master_sisa_records": [
            ("snapshot_id", "master_snapshots"),
            ("source_record_id", "source_records"),
        ],
        "reconciliation_processes": [
            ("master_snapshot_id", "master_snapshots"),
            ("target_batch_id", "upload_batches"),
        ],
        "match_candidates": [("target_record_id", "source_records")],
    }.items():
        existing_keys = {
            tuple(key["constrained_columns"])
            for key in sa.inspect(connection).get_foreign_keys(table)
        }
        absent = [
            (column_name, target)
            for column_name, target in keys
            if (column_name,) not in existing_keys
        ]
        if absent:
            with op.batch_alter_table(table) as batch:
                for column_name, target in absent:
                    batch.create_foreign_key(
                        f"fk_{table}_{column_name}", target, [column_name], ["id"]
                    )

    cast(sa.Table, MatchingRun.__table__).create(connection, checkfirst=True)
    run_columns = {
        column["name"]: column
        for column in sa.inspect(connection).get_columns("matching_runs")
    }
    if "failure_code" not in run_columns:
        op.add_column(
            "matching_runs", sa.Column("failure_code", sa.String(40), nullable=True)
        )
    if not run_columns["max_candidates"]["nullable"]:
        with op.batch_alter_table("matching_runs") as batch:
            batch.alter_column(
                "max_candidates", existing_type=sa.Integer(), nullable=True
            )
    for table, indexed_column in (
        ("master_sisa_records", "snapshot_id"),
        ("match_candidates", "generation"),
    ):
        index = f"ix_{table}_{indexed_column}"
        if index not in {
            item["name"] for item in sa.inspect(connection).get_indexes(table)
        }:
            op.create_index(index, table, [indexed_column])

    # Legacy global rows are retained as one historical snapshot. Their original
    # source batches cannot be inferred, so old processes are not assigned to it.
    count = connection.execute(
        sa.text("SELECT COUNT(*) FROM master_sisa_records WHERE snapshot_id IS NULL")
    ).scalar_one()
    if count:
        snapshot_id = connection.execute(
            sa.text(
                "INSERT INTO master_snapshots (created_at) VALUES (CURRENT_TIMESTAMP) RETURNING id"
            )
        ).scalar_one()
        connection.execute(
            sa.text(
                "UPDATE master_sisa_records SET snapshot_id = :snapshot WHERE snapshot_id IS NULL"
            ),
            {"snapshot": snapshot_id},
        )
    connection.execute(
        sa.text(
            "UPDATE reconciliation_processes SET current_generation = 1 "
            "WHERE current_generation = 0 AND EXISTS (SELECT 1 FROM match_candidates c "
            "WHERE c.process_id = reconciliation_processes.id)"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO matching_runs (process_id, generation, status, radius_meters, "
            "max_candidates, total_targets, matched_targets, created_at, completed_at) "
            "SELECT p.id, 1, p.matching_status, COALESCE(p.radius_meters, 100), NULL, "
            "COALESCE(p.total_targets, 0), COALESCE(p.matched_targets, 0), "
            "COALESCE(p.created_at, CURRENT_TIMESTAMP), p.completed_at "
            "FROM reconciliation_processes p WHERE p.current_generation = 1 "
            "AND NOT EXISTS (SELECT 1 FROM matching_runs r WHERE r.process_id = p.id)"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE matching_runs SET max_candidates = NULL "
            "WHERE EXISTS (SELECT 1 FROM reconciliation_processes p "
            "WHERE p.id = matching_runs.process_id AND p.master_snapshot_id IS NULL "
            "AND p.target_batch_id IS NULL AND p.source_batches IS NULL)"
        )
    )
    if connection.dialect.name == "sqlite":
        if connection.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
            raise RuntimeError("Relasi database tidak konsisten setelah migrasi")
        # SQLite retains deferred DROP TABLE violations even after recreating the
        # parent with identical keys. Reset only after checking the final graph.
        connection.exec_driver_sql("PRAGMA defer_foreign_keys=OFF")
