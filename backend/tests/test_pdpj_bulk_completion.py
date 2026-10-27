"""Audited bulk exceptions unblock correction maps while reserving all PDPJ identities."""

from unittest.mock import Mock

import pytest

from app.config import settings
from app.models.pdpj import PdpjChange, PdpjReview, PdpjRow
from app.models.upload import SourceRecord
from app.modules.pdpj import service
from tests.test_pdpj_validation import action, rows, start, upload
from tests.test_upload_storage import storage_failure


@pytest.fixture
def pending(client, monkeypatch):
    monkeypatch.setattr(service, "VALIDATION_CHUNK_ROWS", 2)
    upload(
        client,
        "dil",
        "IDPEL,NAMA,LAT,LON\n001,A,-6.2,106.8\n002,B,-6.2,106.8\n003,C,-6.2,106.8\n004,Tersisa,-6.2,106.8\n",
    )
    batch = upload(
        client,
        "pdpj",
        "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n009,-6.2,106.8\n003,,\n002,-6.2,106.8\nBAD,-6.2,106.8\n",
    )
    return start(client, batch)["id"]


def request_body(client, review_id, **overrides):
    summary = client.get(f"/pdpj/reviews/{review_id}").json()
    return {
        "revision": summary["revision"],
        "actor": "Petugas Massal",
        "reason": "Referensi belum lengkap; lanjutkan koreksi dengan tindak lanjut tercatat",
        "expected_unresolved": summary["summary"]["unresolved"],
        "confirmed": True,
        **overrides,
    }


def test_bulk_completion_preserves_issues_sources_old_exceptions_and_audit(
    client, db_session, pending
):
    initial = rows(client, pending)
    old = next(row for row in initial if row["fields"]["idpel"] == "009")
    response = client.post(
        f"/pdpj/reviews/{pending}/rows/{old['id']}/decision",
        json=action(
            client, pending, action="exception", reason="Alasan khusus sebelumnya"
        ),
    )
    assert response.status_code == 200
    originals = {
        record.id: dict(record.data) for record in db_session.query(SourceRecord).all()
    }
    before = {row["id"]: row for row in rows(client, pending)}
    body = request_body(client, pending)
    assert body["expected_unresolved"] == 2
    done = client.post(f"/pdpj/reviews/{pending}/complete-with-exceptions", json=body)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed" and done.json()["exceptions_added"] == 2
    summary = client.get(f"/pdpj/reviews/{pending}").json()["summary"]
    assert (
        summary["unresolved"] == 0
        and summary["exceptions"] == 3
        and summary["ready"] == 3
    )
    for row in rows(client, pending):
        assert row["fields"] == before[row["id"]]["fields"]
        assert row["issues"] == before[row["id"]]["issues"]
        assert row["warnings"] == before[row["id"]]["warnings"]
        assert row["reviewed"]
        if row["id"] == old["id"]:
            assert row["exception_reason"] == "Alasan khusus sebelumnya"
        elif row["issues"]:
            assert row["exception"] and row["exception_reason"] == body["reason"]
        else:
            assert not row["exception"]
    changes = db_session.query(PdpjChange).all()
    assert len(changes) == 6
    bulk = [change for change in changes if change.sources.get("bulk")]
    assert len(bulk) == 2
    assert all(
        change.actor == "Petugas Massal"
        and change.reason == body["reason"]
        and change.after["exception"]
        for change in bulk
    )
    assert {
        record.id: record.data for record in db_session.query(SourceRecord).all()
    } == originals
    assert (
        client.post(
            f"/pdpj/reviews/{pending}/complete-with-exceptions", json=body
        ).status_code
        == 409
    )
    assert db_session.query(PdpjChange).count() == 6


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"reason": " "}, 422),
        ({"actor": " "}, 422),
        ({"confirmed": False}, 422),
        ({"expected_unresolved": 999}, 409),
        ({"revision": 0}, 422),
        ({"revision": 999}, 409),
    ],
)
def test_bulk_completion_requires_scope_confirmation_and_fresh_revision(
    client, db_session, pending, overrides, expected
):
    response = client.post(
        f"/pdpj/reviews/{pending}/complete-with-exceptions",
        json=request_body(client, pending, **overrides),
    )
    assert response.status_code == expected, response.text
    db_session.expire_all()
    assert db_session.get(PdpjReview, pending).status == "in_progress"
    assert not any(
        row.exception or row.reviewed
        for row in db_session.query(PdpjRow).filter_by(review_id=pending).all()
    )
    assert db_session.query(PdpjChange).count() == 0


def test_bulk_commit_failure_rolls_back_exceptions_audit_and_completion(
    client, db_session, pending, monkeypatch
):
    body = request_body(client, pending)
    with monkeypatch.context() as patch:
        patch.setattr(db_session, "commit", Mock(side_effect=storage_failure()))
        failed = client.post(
            f"/pdpj/reviews/{pending}/complete-with-exceptions", json=body
        )
    assert failed.status_code == 503, failed.text
    db_session.expire_all()
    assert db_session.get(PdpjReview, pending).status == "in_progress"
    assert db_session.query(PdpjChange).count() == 0
    assert all(not row.exception for row in db_session.query(PdpjRow).all())
    assert (
        client.post(
            f"/pdpj/reviews/{pending}/complete-with-exceptions", json=body
        ).status_code
        == 200
    )


def test_bulk_completion_unblocks_map_and_never_reuses_pdpj_identity(
    client, db_session, pending, monkeypatch
):
    from app.modules.corrections import router

    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(side_effect=RuntimeError("offline")),
    )
    body = request_body(client, pending)
    assert (
        client.post(
            f"/pdpj/reviews/{pending}/complete-with-exceptions", json=body
        ).status_code
        == 200
    )
    target = upload(
        client, "idpel_tidak_ketemu", "IDPEL,NAMA,LAT,LON\n999,Target,-6.2,106.8\n"
    )
    response = client.post(
        "/corrections/idpel_tidak_ketemu/checks",
        json={
            "batch_id": target,
            "pdpj_review_id": pending,
            "radius_meters": 10,
            "actor": "Petugas Uji",
            "request_key": "bulk_exception_map_check",
        },
    )
    assert response.status_code == 200, response.text
    process = response.json()["process_id"]
    record = client.get(
        "/corrections/idpel_tidak_ketemu/records", params={"process_id": process}
    ).json()["items"][0]
    detail = client.get(
        f"/corrections/idpel_tidak_ketemu/records/{record['id']}",
        params={"process_id": process, "radius_meters": 10},
    )
    assert detail.status_code == 200, detail.text
    assert [
        candidate["fields"]["idpel"] for candidate in detail.json()["candidates"]
    ] == ["004"]
