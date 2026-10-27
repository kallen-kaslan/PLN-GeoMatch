"""Reclassify duplicate findings without changing source values or prior decisions."""

from typing import cast

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Connection

DUPLICATE_IDPEL = "idpel_berulang_pdpj"


def upgrade_pdpj_warnings(connection: Connection) -> None:
    from app.models.pdpj import PdpjReview, PdpjRow

    if "warnings" in {
        column["name"] for column in sa.inspect(connection).get_columns("pdpj_rows")
    }:
        return
    op = Operations(MigrationContext.configure(connection))
    op.add_column(
        "pdpj_rows",
        sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"),
    )
    rows = cast(sa.Table, PdpjRow.__table__)
    reviews = cast(sa.Table, PdpjReview.__table__)
    last_id = 0
    changed_reviews: set[int] = set()
    while True:
        found = (
            connection.execute(
                sa.select(rows.c.id, rows.c.review_id, rows.c.issues, rows.c.warnings)
                .where(
                    rows.c.id > last_id,
                    rows.c.review_id.in_(
                        sa.select(reviews.c.id).where(reviews.c.status == "in_progress")
                    ),
                    sa.cast(rows.c.issues, sa.String()).contains(DUPLICATE_IDPEL),
                )
                .order_by(rows.c.id)
                .limit(400)
            )
            .mappings()
            .all()
        )
        if not found:
            break
        pending = []
        for row in found:
            duplicate = [
                item
                for item in (row["issues"] or [])
                if item.get("code") == DUPLICATE_IDPEL
            ]
            if not duplicate:
                continue
            warnings = list(row["warnings"] or [])
            if not any(item.get("code") == DUPLICATE_IDPEL for item in warnings):
                warnings.append(duplicate[0])
            pending.append(
                {
                    "_id": row["id"],
                    "_issues": [
                        item
                        for item in row["issues"]
                        if item.get("code") != DUPLICATE_IDPEL
                    ],
                    "_warnings": warnings,
                }
            )
            changed_reviews.add(row["review_id"])
        if pending:
            connection.execute(
                rows.update()
                .where(rows.c.id == sa.bindparam("_id"))
                .values(
                    issues=sa.bindparam("_issues", type_=sa.JSON()),
                    warnings=sa.bindparam("_warnings", type_=sa.JSON()),
                ),
                pending,
            )
        last_id = found[-1]["id"]
    affected = sorted(changed_reviews)
    for offset in range(0, len(affected), 400):
        connection.execute(
            reviews.update()
            .where(
                reviews.c.id.in_(affected[offset : offset + 400]),
                reviews.c.status == "in_progress",
            )
            .values(revision=reviews.c.revision + 1)
        )
