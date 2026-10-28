"""Approve saved PDPJ data, use frozen versions for corrections, then continue processing."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.correction_decision import CorrectionDecision
from app.models.pdpj import PdpjChange, PdpjReview, PdpjRow
from app.modules.corrections import router as correction_router
from app.modules.pdpj import service
from app.pdpj_publication_schema import upgrade_pdpj_publications
from tests.test_corrections import check
from tests.test_pdpj_progress import finish_steps, step
from tests.test_pdpj_validation import action, rows, upload
from tests.test_upload_storage import storage_failure


@pytest.fixture
def partial(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(service, "VALIDATION_CHUNK_ROWS", 2)
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        correction_router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(side_effect=RuntimeError("offline")),
    )
    upload(
        client,
        "dil",
        "IDPEL,LAT,LON\n" + "".join(f"{i:03},-6.2,106.8\n" for i in range(1, 6)),
    )
    batch = upload(
        client,
        "pdpj",
        "IDPEL,NAMA,LAT,LON\n001,Satu,-6.2,106.8\n002,Dua,-6.2,106.8\n003,Tiga,-6.2,106.8\n",
    )
    created = client.post(
        "/pdpj/reviews", json={"batch_id": batch, "incremental": True}
    ).json()
    checkpoint = step(client, created)
    return client.post(f"/pdpj/reviews/{checkpoint['id']}/pause").json()


def approve(client: TestClient, review_id: int) -> dict:
    response = client.post(
        f"/pdpj/reviews/{review_id}/complete", json=action(client, review_id)
    )
    assert response.status_code == 200, response.json()
    return response.json()


def test_partial_publication_keeps_cursor_and_pins_corrections_until_next_version(
    client: TestClient,
    db_session: Session,
    partial: dict,
) -> None:
    review_id = partial["id"]
    path = f"/pdpj/reviews/{review_id}"
    cursor = partial["processing"].copy()
    published = approve(client, review_id)
    first = published["published_review"]
    assert published["status"] == "in_progress"
    assert published["processing"] == cursor
    assert first["source_review_id"] == review_id
    assert first["publication"]["row_count"] == 2
    assert first["publication"]["version"] == 1
    assert first["publication"]["is_partial"] is True
    assert first["status"] == "completed"
    assert len(rows(client, first["id"])) == 2
    assert (
        client.get(f"/pdpj/batches/{partial['batch_id']}/reviews").json()[0]["id"]
        == review_id
    )
    assert (
        client.post(
            "/pdpj/reviews", json={"batch_id": partial["batch_id"], "incremental": True}
        ).json()["id"]
        == review_id
    )
    original_fields = rows(client, first["id"])
    assert client.get("/corrections/ready-pdpj").json()[0]["review_id"] == first["id"]

    target = upload(client, "idpel_kosong", "IDPEL,NAMA,LAT,LON\n,Target,-6.2,106.8\n")
    result = check(client, "idpel_kosong", target, first["id"])
    process_id = result["process_id"]
    base = f"/corrections/idpel_kosong/checks/{process_id}"
    target_row = client.get(
        "/corrections/idpel_kosong/records", params={"process_id": process_id}
    ).json()["items"][0]
    detail = client.get(
        f"/corrections/idpel_kosong/records/{target_row['id']}",
        params={"process_id": process_id},
    ).json()
    assert {candidate["fields"]["idpel"] for candidate in detail["candidates"]} == {
        "004",
        "005",
    }
    candidate = next(
        item for item in detail["candidates"] if item["fields"]["idpel"] == "004"
    )
    chosen = client.post(
        base + f"/records/{target_row['id']}/choice",
        json={
            "generation": 1,
            "expected_revision": 0,
            "candidate_id": candidate["id"],
            "actor": "Petugas",
            "request_key": "publication_choice_1",
        },
    )
    assert chosen.status_code == 200, chosen.json()
    choice = chosen.json()

    resumed = client.post(path + "/resume").json()
    progressed = step(client, resumed)
    assert progressed["processing"]["processed_rows"] == 3
    client.post(path + "/pause")
    last = rows(client, review_id)[-1]
    changed = client.patch(
        path + f"/rows/{last['id']}",
        json=action(
            client,
            review_id,
            fields={"idpel": "004"},
            reason="Identitas dikonfirmasi",
        ),
    )
    assert changed.status_code == 200, changed.json()
    second = approve(client, review_id)["published_review"]
    assert second["publication"]["row_count"] == 3
    assert second["publication"]["version"] == 2
    assert rows(client, first["id"]) == original_fields
    assert client.get(base + f"/records/{target_row['id']}/choice").json() == choice
    update = client.get(base).json()
    assert update["pdpj_review_id"] == first["id"]
    assert update["pdpj_update"]["review_id"] == second["id"]
    assert update["pdpj_update"]["conflicts"] == [
        {"record_id": target_row["id"], "codes": ["idpel_sama_pdpj"]}
    ]
    latest = check(
        client, "idpel_kosong", target, second["id"], key="new_published_version"
    )
    latest_detail = client.get(
        f"/corrections/idpel_kosong/records/{target_row['id']}",
        params={"process_id": latest["process_id"]},
    ).json()
    assert {item["fields"]["idpel"] for item in latest_detail["candidates"]} == {
        "003",
        "005",
    }
    final = finish_steps(client, client.post(path + "/resume").json())
    assert (
        final["processing"]["last_source_id"]
        == progressed["processing"]["last_source_id"]
    )
    assert len(rows(client, review_id)) == 3
    completed = approve(client, review_id)
    assert completed["status"] == "completed"
    assert completed["publication"]["version"] == 3
    assert db_session.query(CorrectionDecision).count() == 1
    assert client.get(base).json()["pdpj_review_id"] == first["id"]


def test_partial_snapshot_copies_evidence_and_allows_reviewing_saved_rows(
    client: TestClient,
    partial: dict,
) -> None:
    path = f"/pdpj/reviews/{partial['id']}"
    row = rows(client, partial["id"])[0]
    response = client.patch(
        path + f"/rows/{row['id']}",
        json=action(
            client,
            partial["id"],
            fields={"nama": "Sudah ditinjau"},
            reason="Konfirmasi",
        ),
    )
    assert response.status_code == 200
    frozen = approve(client, partial["id"])["published_review"]
    copied = rows(client, frozen["id"])[0]
    detail = client.get(f"/pdpj/reviews/{frozen['id']}/rows/{copied['id']}").json()
    assert detail["fields"]["nama"] == "Sudah ditinjau"
    assert detail["recommendations_total"] == 1
    assert any(event["action"] == "manual" for event in detail["history"])
    assert (
        client.patch(
            f"/pdpj/reviews/{frozen['id']}/rows/{copied['id']}",
            json=action(client, frozen["id"], fields={"nama": "Diubah"}, reason="Tes"),
        ).status_code
        == 409
    )


def test_partial_approval_failure_keeps_checkpoint_and_creates_no_version(
    client: TestClient,
    db_session: Session,
    partial: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = f"/pdpj/reviews/{partial['id']}"
    before = db_session.query(PdpjChange).count()
    body = action(client, partial["id"])
    with monkeypatch.context() as patch:
        patch.setattr(db_session, "commit", Mock(side_effect=storage_failure()))
        response = client.post(path + "/complete", json=body)
    assert response.status_code == 503
    db_session.expire_all()
    assert (
        db_session.query(PdpjReview)
        .filter(PdpjReview.source_review_id.isnot(None))
        .count()
        == 0
    )
    assert db_session.query(PdpjChange).count() == before
    assert client.get(path).json()["processing"] == partial["processing"]
    assert not any(row.reviewed for row in db_session.query(PdpjRow).all())
    assert client.post(path + "/complete", json=body).status_code == 200


def test_partial_exceptions_are_explicit_and_snapshot_approval_is_idempotent(
    client: TestClient,
    partial: dict,
) -> None:
    path = f"/pdpj/reviews/{partial['id']}"
    row = rows(client, partial["id"])[0]
    changed = client.patch(
        path + f"/rows/{row['id']}",
        json=action(
            client,
            partial["id"],
            fields={"lat": None},
            reason="Perlu survei ulang",
        ),
    )
    assert changed.status_code == 200
    assert (
        client.post(path + "/complete", json=action(client, partial["id"])).status_code
        == 409
    )
    approved = client.post(
        path + "/complete-with-exceptions",
        json=action(
            client,
            partial["id"],
            expected_unresolved=1,
            reason="Menunggu survei",
            confirmed=True,
        ),
    )
    assert approved.status_code == 200, approved.json()
    result = approved.json()
    assert result["status"] == "in_progress"
    snapshot = result["published_review"]
    saved = rows(client, snapshot["id"])[0]
    assert saved["exception"] is True and saved["exception_reason"] == "Menunggu survei"
    repeated = approve(client, partial["id"])
    assert repeated["published_review"]["id"] == snapshot["id"]
    assert len(client.get(path).json()["publications"]) == 1
    assert (
        client.post(
            path + "/complete",
            json={"revision": partial["revision"], "actor": "Petugas"},
        ).status_code
        == 409
    )
    finish_steps(client, client.post(path + "/resume").json())
    assert rows(client, snapshot["id"])[0] == saved


def test_pending_identity_is_also_a_target_conflict(
    client: TestClient, partial: dict
) -> None:
    snapshot = approve(client, partial["id"])["published_review"]
    target = upload(client, "idpel_tidak_ketemu", "IDPEL,LAT,LON\n003,-6.2,106.8\n")
    result = check(client, "idpel_tidak_ketemu", target, snapshot["id"])
    item = client.get(
        "/corrections/idpel_tidak_ketemu/records",
        params={"process_id": result["process_id"]},
    ).json()["items"][0]
    assert item["search_status"] == "pdpj_conflict"
    assert item["conflicts"][0]["pending_validation"] is True
    assert item["candidate_count"] == 0


def test_publication_upgrade_keeps_legacy_reviews_and_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE pdpj_reviews (id INTEGER PRIMARY KEY, status VARCHAR)")
        )
        connection.execute(text("INSERT INTO pdpj_reviews VALUES (1, 'completed')"))
        upgrade_pdpj_publications(connection)
        upgrade_pdpj_publications(connection)
        assert connection.execute(
            text("SELECT status, source_review_id, publication FROM pdpj_reviews")
        ).one() == ("completed", None, None)
        assert "ix_pdpj_reviews_source_review_id" in {
            index["name"] for index in inspect(connection).get_indexes("pdpj_reviews")
        }
    engine.dispose()
