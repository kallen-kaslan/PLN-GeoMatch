"""Deep pages fetch only selected row payloads and preserve filters and ordering."""

from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Table, event, inspect
from sqlalchemy.orm import Session

from app.models.pdpj import PdpjRow
from app.pdpj_results_schema import upgrade_pdpj_results
from tests.test_pdpj_validation import upload


@pytest.mark.parametrize(
    "status,total,first_row,index",
    [
        ("all", 100, 32, "ix_pdpj_rows_review_row_number_id"),
        ("not_found", 50, 82, "ix_pdpj_rows_review_existence_row_number_id"),
    ],
)
def test_pages_use_ordered_covering_index_and_keep_original_fields_out_of_payload(
    client: TestClient,
    db_session: Session,
    status: str,
    total: int,
    first_row: int,
    index: str,
) -> None:
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    batch = upload(
        client,
        "pdpj",
        "IDPEL,NAMA,LAT,LON\n"
        + "".join(
            f"{'001' if i < 50 else '999'},Target {i},-6.2,106.8\n" for i in range(100)
        ),
    )
    review = client.post("/pdpj/reviews", json={"batch_id": batch}).json()
    queries = []

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        if (
            statement.lstrip().startswith("SELECT")
            and "JOIN (SELECT pdpj_rows.id" in statement
        ):
            queries.append((statement, parameters))

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        response = client.get(
            f"/pdpj/reviews/{review['id']}/rows",
            params={"status": status, "skip": 30, "limit": 10},
        )
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)
    assert response.status_code == 200, response.json()
    result = response.json()
    assert result["total"] == total
    assert [row["row_number"] for row in result["items"]] == list(
        range(first_row, first_row + 10)
    )
    assert all("original_fields" not in row for row in result["items"])
    assert len(queries) == 1
    statement, parameters = queries[0]
    assert "pdpj_rows.original_fields" not in statement
    plan = (
        db_session.connection()
        .exec_driver_sql("EXPLAIN QUERY PLAN " + statement, parameters)
        .all()
    )
    assert any("USING COVERING INDEX " + index in row[3] for row in plan)
    assert (
        len(
            client.get(
                f"/pdpj/reviews/{review['id']}/rows",
                params={"status": status, "skip": total},
            ).json()["items"]
        )
        == 0
    )


def test_paging_index_upgrade_is_additive_and_repeatable(
    client: TestClient, db_session: Session
) -> None:
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    batch = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n999,,\n")
    assert client.post("/pdpj/reviews", json={"batch_id": batch}).status_code == 200
    table = cast(Table, PdpjRow.__table__)
    expected = {
        "ix_pdpj_rows_review_row_number_id",
        "ix_pdpj_rows_review_existence_row_number_id",
    }
    before = db_session.execute(table.select()).all()
    assert len(before) == 2
    connection = db_session.connection()
    for index in table.indexes:
        if index.name in expected:
            index.drop(connection)
    upgrade_pdpj_results(connection)
    upgrade_pdpj_results(connection)
    assert expected <= {
        index["name"] for index in inspect(connection).get_indexes("pdpj_rows")
    }
    assert db_session.execute(table.select()).all() == before
