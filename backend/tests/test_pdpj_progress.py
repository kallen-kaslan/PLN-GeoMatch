"""Durable chunk boundaries, stop/resume, recovery, and partial-result isolation."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.pdpj import PdpjRecommendation, PdpjReview, PdpjRow
from app.modules.pdpj import service
from app.pdpj_progress_schema import upgrade_pdpj_progress
from tests.test_pdpj_validation import upload


@pytest.fixture
def pending(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(service, "VALIDATION_CHUNK_ROWS", 2)
    master = upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.3,106.9\n")
    batch = upload(
        client,
        "pdpj",
        "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.3,106.9\n001,-6.4,107.0\n",
    )
    result = client.post(
        "/pdpj/reviews",
        json={
            "batch_id": batch,
            "master_batch_ids": [master],
            "incremental": True,
        },
    )
    assert result.status_code == 200
    review = result.json()
    assert review["processing"]["processed_rows"] == 0
    return review


def step(client: TestClient, review: dict) -> dict:
    response = client.post(
        f"/pdpj/reviews/{review['id']}/advance", json={"revision": review["revision"]}
    )
    assert response.status_code == 200, response.json()
    return response.json()


def finish_steps(client: TestClient, review: dict) -> dict:
    for _ in range(10):
        if review["processing"]["state"] == "ready":
            return review
        review = step(client, review)
    pytest.fail("Checkpoint did not finish")


def test_pause_reload_resume_preserves_rows_and_finishes_validation(
    client: TestClient,
    db_session: Session,
    pending: dict,
) -> None:
    review = step(client, pending)
    path = f"/pdpj/reviews/{review['id']}"
    assert review["processing"]["processed_rows"] == 2
    assert review["processing"]["last_row_number"] == 3
    first_rows = client.get(path + "/rows").json()["items"]
    assert [row["existence"] for row in first_rows] == ["found", "found"]
    original_ids = [row["id"] for row in first_rows]
    # Read from another session, rather than the request session's identity map.
    with Session(db_session.get_bind()) as other:
        saved = other.get(PdpjReview, review["id"])
        assert (
            saved.processing["last_source_id"] == review["processing"]["last_source_id"]
        )
        assert other.query(PdpjRow).filter_by(review_id=review["id"]).count() == 2
    paused = client.post(path + "/pause").json()
    assert paused["processing"]["state"] == "paused"
    assert (
        client.post(
            path + "/advance", json={"revision": paused["revision"]}
        ).status_code
        == 409
    )
    reloaded = client.get(path).json()
    assert reloaded["processing"]["processed_rows"] == 2
    resumed = client.post(path + "/resume").json()
    matched = step(client, resumed)
    assert matched["processing"]["processed_rows"] == 3
    assert matched["processing"]["stage"] == "validating"
    # Final validation also resumes by cursor, without rematching source rows.
    validating = step(client, matched)
    assert validating["processing"]["validated_rows"] == 2
    client.post(path + "/pause")
    ready = finish_steps(client, client.post(path + "/resume").json())
    assert ready["processing"]["validated_rows"] == 3
    final_rows = client.get(path + "/rows").json()["items"]
    assert [row["id"] for row in final_rows[:2]] == original_ids
    assert len(final_rows) == 3
    assert final_rows[0]["warnings"] == final_rows[2]["warnings"]
    assert final_rows[0]["warnings"][0]["code"] == "idpel_berulang_pdpj"
    assert client.get(path).json()["summary"]["found"] == 3
    with Session(db_session.get_bind()) as other:
        assert other.query(PdpjRecommendation).count() == 3


def test_failed_chunk_rolls_back_without_losing_previous_checkpoint(
    client: TestClient,
    db_session: Session,
    pending: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = step(client, pending)
    path = f"/pdpj/reviews/{review['id']}"
    original = service.add_recommendations

    def fail_after_insert(db: Session, item: PdpjReview, rows: list[PdpjRow]) -> None:
        original(db, item, rows)
        raise RuntimeError("Simulated interruption after recommendation insert")

    monkeypatch.setattr(service, "add_recommendations", fail_after_insert)
    response = client.post(path + "/advance", json={"revision": review["revision"]})
    assert response.status_code == 500
    saved = client.get(path).json()
    assert saved["processing"]["state"] == "failed"
    assert (
        saved["processing"]["last_source_id"] == review["processing"]["last_source_id"]
    )
    assert saved["processing"]["processed_rows"] == 2
    assert (
        db_session.query(PdpjRow).count()
        == db_session.query(PdpjRecommendation).count()
        == 2
    )
    monkeypatch.setattr(service, "add_recommendations", original)
    finished = finish_steps(client, client.post(path + "/resume").json())
    assert finished["processing"]["processed_rows"] == 3
    assert (
        db_session.query(PdpjRow).count()
        == db_session.query(PdpjRecommendation).count()
        == 3
    )


def test_stale_steps_and_partial_completion_cannot_change_results(
    client: TestClient,
    pending: dict,
) -> None:
    path = f"/pdpj/reviews/{pending['id']}"
    review = step(client, pending)
    assert (
        client.post(
            path + "/advance", json={"revision": pending["revision"]}
        ).status_code
        == 409
    )
    assert client.get(path).json()["processing"]["processed_rows"] == 2
    body = {"revision": review["revision"], "actor": "Petugas"}
    assert client.post(path + "/complete", json=body).status_code == 409
    assert (
        client.post(
            path + "/complete-with-exceptions",
            json={
                **body,
                "reason": "Belum diperiksa semua",
                "expected_unresolved": 1,
                "confirmed": True,
            },
        ).status_code
        == 409
    )
    row = client.get(path + "/rows").json()["items"][0]
    assert (
        client.patch(
            path + f"/rows/{row['id']}", json={**body, "fields": {"nama": "Baru"}}
        ).status_code
        == 409
    )
    # Starting again finds the same checkpoint and pins the original master list.
    same = client.post(
        "/pdpj/reviews", json={"batch_id": pending["batch_id"], "incremental": True}
    ).json()
    assert same["id"] == pending["id"]
    assert (
        client.post(
            "/pdpj/reviews",
            json={
                "batch_id": pending["batch_id"],
                "master_batch_ids": [],
                "incremental": True,
            },
        ).status_code
        == 422
    )
    ready = finish_steps(client, review)
    assert (
        client.post(
            path + "/complete", json={"revision": ready["revision"], "actor": "Petugas"}
        ).status_code
        == 200
    )


def test_progress_schema_upgrade_is_additive_and_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE pdpj_reviews (id INTEGER PRIMARY KEY, status VARCHAR)")
        )
        connection.execute(
            text("INSERT INTO pdpj_reviews (id, status) VALUES (1, 'completed')")
        )
        upgrade_pdpj_progress(connection)
        upgrade_pdpj_progress(connection)
        assert connection.execute(
            text("SELECT status, processing FROM pdpj_reviews")
        ).one() == ("completed", None)
    engine.dispose()
