"""Repeated PDPJ identities are informational and retain every source observation."""

from unittest.mock import Mock

import pytest

from app.config import settings
from app.models.pdpj import PdpjChange, PdpjReview, PdpjRow
from app.models.upload import SourceRecord
from app.modules.corrections import router as correction_router
from app.pdpj_warning_schema import DUPLICATE_IDPEL, upgrade_pdpj_warnings
from tests.test_pdpj_validation import action, rows, start, upload


@pytest.mark.parametrize(
    "second_location,second_type",
    [
        ("-6.2,106.8", "PRABAYAR"),
        ("-7.3,108.2", "PRABAYAR"),
        ("-7.3,108.2", "PASCABAYAR"),
    ],
)
def test_duplicate_identity_with_different_locations_or_service_can_complete(
    client,
    db_session,
    monkeypatch,
    second_location,
    second_type,
):
    upload(
        client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n003,-6.2,106.8\n"
    )
    batch_id = upload(
        client,
        "pdpj",
        "IDPEL,NAMA,LAT,LON,JENISLAYANAN\n001,Pertama,-6.2,106.8,PRABAYAR\n"
        + f"001,Kedua,{second_location},{second_type}\n"
        + "002,Lain,-6.2,106.8,PRABAYAR\n",
    )
    raw = {
        record.id: dict(record.data) for record in db_session.query(SourceRecord).all()
    }
    review_id = start(client, batch_id)["id"]
    summary = client.get(f"/pdpj/reviews/{review_id}").json()["summary"]
    assert summary["total_rows"] == summary["ready"] == 3
    assert summary["unresolved"] == summary["exceptions"] == 0
    items = rows(client, review_id)
    assert all(not row["issues"] for row in items)
    assert [len(row["warnings"]) for row in items] == [1, 1, 0]
    assert all(row["warnings"][0]["code"] == DUPLICATE_IDPEL for row in items[:2])
    assert items[1]["fields"]["jenis_pel"] == second_type
    assert (items[1]["fields"]["lat"], items[1]["fields"]["lon"]) == tuple(
        map(float, second_location.split(","))
    )
    approved = client.post(
        f"/pdpj/reviews/{review_id}/rows/{items[0]['id']}/decision",
        json=action(client, review_id, action="reviewed"),
    )
    assert approved.status_code == 200, approved.text
    completed = client.post(
        f"/pdpj/reviews/{review_id}/complete", json=action(client, review_id)
    )
    assert completed.status_code == 200, completed.text
    assert all(
        row["reviewed"] and not row["exception"] for row in rows(client, review_id)
    )
    assert {
        record.id: record.data for record in db_session.query(SourceRecord).all()
    } == raw
    assert db_session.query(PdpjChange).filter_by(action="exception").count() == 0
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        correction_router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(side_effect=RuntimeError("offline")),
    )
    target = upload(client, "idpel_tidak_ketemu", "IDPEL,LAT,LON\n999,-6.2,106.8\n")
    checked = client.post(
        "/corrections/idpel_tidak_ketemu/checks",
        json={
            "batch_id": target,
            "pdpj_review_id": review_id,
            "actor": "Petugas Uji",
            "request_key": "duplicates_allowed_check",
            "radius_meters": 30,
        },
    ).json()
    assert checked["status"] == "completed"
    record = client.get(
        "/corrections/idpel_tidak_ketemu/records",
        params={"process_id": checked["process_id"]},
    ).json()["items"][0]
    detail = client.get(
        f"/corrections/idpel_tidak_ketemu/records/{record['id']}",
        params={"process_id": checked["process_id"]},
    ).json()
    assert [candidate["fields"]["idpel"] for candidate in detail["candidates"]] == [
        "003"
    ]


@pytest.mark.parametrize("status", ["in_progress", "completed"])
def test_legacy_duplicate_migration_reclassifies_open_reviews_and_keeps_history(
    client,
    db_session,
    status,
):
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    batch_id = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n001,,\n")
    review_id = start(client, batch_id)["id"]
    records = db_session.query(PdpjRow).order_by(PdpjRow.id).all()
    expected_issues = {}
    for row in records:
        row.issues = [*row.issues, {"field": "idpel", "code": DUPLICATE_IDPEL}]
        expected_issues[row.id] = list(row.issues)
        row.reviewed = row.exception = status == "completed"
        row.exception_reason = "Keputusan lama" if row.exception else ""
    review = db_session.get(PdpjReview, review_id)
    review.status = status
    revision = review.revision
    db_session.add(
        PdpjChange(
            row_id=records[0].id,
            action="exception",
            actor="Petugas lama",
            reason="Audit lama",
            before={"fields": dict(records[0].current_fields)},
            after={"fields": dict(records[0].current_fields)},
            sources={},
        )
    )
    db_session.commit()
    source_fields = {row.id: dict(row.current_fields) for row in records}
    with db_session.get_bind().begin() as connection:
        connection.exec_driver_sql("ALTER TABLE pdpj_rows DROP COLUMN warnings")
        upgrade_pdpj_warnings(connection)
        upgrade_pdpj_warnings(connection)
    db_session.expire_all()
    stored = db_session.query(PdpjRow).order_by(PdpjRow.id).all()
    assert {row.id: row.current_fields for row in stored} == source_fields
    assert db_session.query(PdpjChange).count() == 1
    assert db_session.query(PdpjChange).one().reason == "Audit lama"
    assert db_session.get(PdpjReview, review_id).revision == revision + int(
        status == "in_progress"
    )
    if status == "in_progress":
        assert all(
            row.warnings == [{"field": "idpel", "code": DUPLICATE_IDPEL}]
            for row in stored
        )
        assert stored[0].issues == []
        assert all(item["code"] != DUPLICATE_IDPEL for item in stored[1].issues)
        summary = client.get(f"/pdpj/reviews/{review_id}").json()["summary"]
        assert summary["unresolved"] == 1 and summary["ready"] == 1
        assert (
            client.post(
                f"/pdpj/reviews/{review_id}/complete",
                json={"actor": "Petugas", "revision": revision},
            ).status_code
            == 409
        )
    else:
        assert all(row.issues == expected_issues[row.id] for row in stored)
        assert all(
            row.exception and row.reviewed and row.exception_reason == "Keputusan lama"
            for row in stored
        )
        assert db_session.get(PdpjReview, review_id).status == "completed"
    assert all(
        item["warnings"]
        and all(issue["code"] != DUPLICATE_IDPEL for issue in item["issues"])
        for item in rows(client, review_id)
    )
