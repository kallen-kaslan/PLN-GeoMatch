"""End-to-end validation, corrections, audit, isolation, and downstream PDPJ gating."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.master_sisa import MasterSisaRecord
from app.models.matching import ReconciliationProcess
from app.models.pdpj import PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow
from app.models.upload import SourceRecord
from app.modules.spatial.pipeline import execute_pipeline, pin_pipeline_sources
from app.pdpj_schema import upgrade_pdpj_validation


def upload(client: TestClient, kind: str, content: str, name: str = "data.csv") -> int:
    response = client.post(
        "/upload/",
        data={"dataset_type": kind},
        files={"file": (name, content.encode(), "text/csv")},
    )
    assert response.status_code == 200
    batch_id = response.json()["id"]
    assert (
        client.post(
            "/upload/confirm-mapping",
            json={"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
        ).status_code
        == 200
    )
    return batch_id


def start(client: TestClient, batch_id: int, masters: list[int] | None = None) -> dict:
    response = client.post(
        "/pdpj/reviews", json={"batch_id": batch_id, "master_batch_ids": masters}
    )
    assert response.status_code == 200, response.json()
    return response.json()


def rows(client: TestClient, review_id: int) -> list[dict]:
    return client.get(f"/pdpj/reviews/{review_id}/rows").json()["items"]


def action(client: TestClient, review_id: int, **kwargs: object) -> dict:
    revision = client.get(f"/pdpj/reviews/{review_id}").json()["revision"]
    return {"revision": revision, "actor": "Petugas Uji", **kwargs}


def test_identity_completeness_all_recommendations_filters_and_provenance(
    client: TestClient,
) -> None:
    first = upload(
        client, "prabayar", "IDPEL,NAMA,LAT,LON\n001,A,,\n002,B,-6.2,106.8\n"
    )
    second = upload(
        client,
        "dil",
        "IDPEL,V_BULAN_REKAP,NOMOR_GARDU,KOORDINAT_Y,KOORDINAT_X\n001,202610,G1,-6.3,106.9\n001,202609,G0,bad,106.8\n003,202610,G3,,\n",
        "dil.csv",
    )
    batch_id = upload(
        client,
        "pdpj",
        "IDPEL,NAMA,LAT,LON\n001,A,,\n009,X,-6.2,106.8\n,,,\nBAD,Y,-6.2,106.8\n002,B,-6.2,106.8\n003,C,,\n",
    )
    assert client.get("/pdpj/batches").json()[0]["id"] == batch_id
    assert client.get(f"/pdpj/batches/{batch_id}").json()["headers"] == [
        "IDPEL",
        "NAMA",
        "LAT",
        "LON",
    ]
    review = start(client, batch_id)
    assert review["master_batch_ids"] == [first, second]
    assert start(client, batch_id)["id"] == review["id"]
    info = client.get(f"/pdpj/reviews/{review['id']}").json()
    assert info["summary"] == {
        "total_rows": 6,
        "found": 3,
        "not_found": 1,
        "empty": 1,
        "invalid": 1,
        "incomplete_coordinates": 3,
        "exceptions": 0,
        "unresolved": 5,
        "ready": 1,
    }
    items = rows(client, review["id"])
    detail = client.get(
        f"/pdpj/reviews/{review['id']}/rows/{items[0]['id']}?limit=2"
    ).json()
    assert detail["recommendations_total"] == 3 and len(detail["recommendations"]) == 2
    assert detail["raw_data"]["IDPEL"] == "001"
    page = client.get(
        f"/pdpj/reviews/{review['id']}/rows/{items[0]['id']}?skip=2"
    ).json()
    assert page["recommendations"][0]["validation_errors"][0]["field"] == "lat"
    assert detail["recommendations"][1]["provenance"]["filename"] == "dil.csv"
    assert detail["recommendations"][1]["fields"]["kode_gardu"] == "G1"
    for status, count in (
        ("found", 3),
        ("not_found", 1),
        ("empty", 1),
        ("invalid", 1),
        ("incomplete", 3),
        ("unresolved", 5),
        ("ready", 1),
        ("exception", 0),
    ):
        assert (
            client.get(
                f"/pdpj/reviews/{review['id']}/rows?status={status}&limit=1"
            ).json()["total"]
            == count
        )
    assert client.get(f"/pdpj/reviews/{review['id']}/rows?q=002").json()["total"] == 1
    assert client.get(f"/pdpj/reviews/{review['id']}/rows?q=%25").json()["total"] == 0
    assert (
        client.get(f"/pdpj/batches/{batch_id}/reviews").json()[0]["id"] == review["id"]
    )


def test_selected_fields_manual_changes_history_overwrite_and_completion(
    client: TestClient, db_session: Session
) -> None:
    master = upload(
        client, "dil", "IDPEL,NAMA,LAT,LON,NOMOR_GARDU\n001,Rekomendasi,-6.2,106.8,G1\n"
    )
    batch_id = upload(client, "pdpj", "IDPEL,NAMA,LAT,LON\n001,Nama Asli,,\n")
    review = start(client, batch_id)
    review_id = review["id"]
    row = rows(client, review_id)[0]
    path = f"/pdpj/reviews/{review_id}/rows/{row['id']}"
    candidate = client.get(path).json()["recommendations"][0]
    assert (
        client.post(
            f"/pdpj/reviews/{review_id}/complete", json=action(client, review_id)
        ).status_code
        == 409
    )
    assert (
        client.post(
            path + "/apply",
            json=action(
                client, review_id, recommendation_id=candidate["id"], fields=["nama"]
            ),
        ).status_code
        == 409
    )
    result = client.post(
        path + "/apply",
        json=action(
            client,
            review_id,
            recommendation_id=candidate["id"],
            fields=["lat", "lon", "kode_gardu"],
        ),
    )
    assert result.status_code == 200 and result.json()["fields"]["nama"] == "Nama Asli"
    assert (
        client.patch(
            path,
            json={
                "revision": 1,
                "actor": "Uji",
                "fields": {"nama": "stale"},
                "reason": "ganti",
            },
        ).status_code
        == 409
    )
    assert (
        client.patch(
            path, json=action(client, review_id, fields={"lat": 100})
        ).status_code
        == 409
    )
    assert (
        client.patch(
            path, json=action(client, review_id, fields={"lat": 100}, reason="koreksi")
        ).status_code
        == 422
    )
    assert (
        client.patch(
            path,
            json=action(
                client,
                review_id,
                fields={"nama": "Nama Manual"},
                reason="Konfirmasi pelanggan",
            ),
        ).status_code
        == 200
    )
    detail = client.get(path).json()
    assert len(detail["history"]) == 2
    assert detail["history"][1]["sources"]["lat"]["batch_id"] == master
    assert detail["history"][0]["before"]["fields"]["nama"] == "Nama Asli"
    source = db_session.get(SourceRecord, row["source_record_id"])
    assert source.data == {"IDPEL": "001", "NAMA": "Nama Asli", "LAT": "", "LON": ""}
    assert (
        client.post(
            path + "/decision", json=action(client, review_id, action="reviewed")
        ).status_code
        == 200
    )
    complete = client.post(
        f"/pdpj/reviews/{review_id}/complete", json=action(client, review_id)
    )
    assert (
        complete.status_code == 200 and complete.json()["completed_by"] == "Petugas Uji"
    )
    assert (
        client.patch(
            path, json=action(client, review_id, fields={"nama": "x"}, reason="x")
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/upload/confirm-mapping",
            json={"batch_id": master, "column_mapping": {"idpel": "NAMA"}},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/upload/confirm-mapping",
            json={"batch_id": batch_id, "column_mapping": {"idpel": "NAMA"}},
        ).status_code
        == 409
    )
    next_review = start(client, batch_id)
    next_row = rows(client, next_review["id"])[0]
    assert (
        next_review["id"] != review_id and next_row["fields"]["nama"] == "Nama Manual"
    )
    assert client.get(path).json()["fields"]["nama"] == "Nama Manual"
    assert (
        client.get(f"/pdpj/reviews/{next_review['id']}/rows/{next_row['id']}").json()[
            "history"
        ][0]["action"]
        == "carried_forward"
    )


def test_manual_idpel_change_loads_new_sources_and_retains_previous_recommendations(
    client: TestClient,
) -> None:
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.3,106.9\n")
    batch_id = upload(client, "pdpj", "IDPEL,LAT,LON\n001,,\n")
    review_id = start(client, batch_id)["id"]
    row = rows(client, review_id)[0]
    path = f"/pdpj/reviews/{review_id}/rows/{row['id']}"
    old_candidate = client.get(path).json()["recommendations"][0]
    assert (
        client.patch(
            path,
            json=action(
                client, review_id, fields={"idpel": "002"}, reason="Perbaikan IDPEL"
            ),
        ).status_code
        == 200
    )
    detail = client.get(path).json()
    assert detail["existence"] == "found" and detail["recommendation_count"] == 1
    assert (
        detail["recommendations_total"] == 2
        and not detail["recommendations"][0]["current"]
    )
    assert (
        client.post(
            path + "/apply",
            json=action(
                client,
                review_id,
                recommendation_id=old_candidate["id"],
                fields=["lat", "lon"],
            ),
        ).status_code
        == 409
    )
    candidate = detail["recommendations"][1]
    assert (
        client.post(
            path + "/apply",
            json=action(
                client,
                review_id,
                recommendation_id=candidate["id"],
                fields=["lat", "lon"],
            ),
        ).status_code
        == 200
    )
    assert client.get(path).json()["fields"]["lat"] == -6.3


def test_duplicate_warning_allows_approval_but_invalid_values_require_resolution(
    client: TestClient,
) -> None:
    upload(client, "dil", "IDPEL,LAT,LON\n001,bad,106.8\n")
    batch_id = upload(
        client, "pdpj", "IDPEL,LAT,LON,DAYA\n001,-6.2,106.8,bad\n001,-6.2,106.8,900\n"
    )
    review_id = start(client, batch_id)["id"]
    items = rows(client, review_id)
    assert any(item["code"] == "daya_tidak_valid" for item in items[0]["issues"])
    for row in items:
        path = f"/pdpj/reviews/{review_id}/rows/{row['id']}"
        assert any(item["code"] == "idpel_berulang_pdpj" for item in row["warnings"])
        assert client.post(
            path + "/decision", json=action(client, review_id, action="reviewed")
        ).status_code == (409 if row["issues"] else 200)
        if not row["issues"]:
            continue
        assert (
            client.post(
                path + "/decision", json=action(client, review_id, action="exception")
            ).status_code
            == 422
        )
        assert (
            client.post(
                path + "/decision",
                json=action(
                    client,
                    review_id,
                    action="exception",
                    reason="Duplikasi sudah ditinjau petugas",
                ),
            ).status_code
            == 200
        )
    path = f"/pdpj/reviews/{review_id}/rows/{items[0]['id']}"
    assert (
        client.post(
            path + "/decision", json=action(client, review_id, action="reopen")
        ).status_code
        == 200
    )
    candidate = client.get(path).json()["recommendations"][0]
    assert (
        client.post(
            path + "/apply",
            json=action(
                client,
                review_id,
                recommendation_id=candidate["id"],
                fields=["lat"],
                overwrite=True,
                reason="ganti",
            ),
        ).status_code
        == 422
    )
    assert (
        client.post(
            path + "/decision",
            json=action(
                client,
                review_id,
                action="exception",
                reason="Menunggu konfirmasi lapangan",
            ),
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/pdpj/reviews/{review_id}/complete", json=action(client, review_id)
        ).status_code
        == 200
    )


def test_completed_validation_gates_pipeline_and_excludes_corrected_identities(
    client: TestClient, db_session: Session
) -> None:
    master = upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.3,106.9\n")
    batch_id = upload(client, "pdpj", "IDPEL,LAT,LON\n999,-6.2,106.8\n")
    with pytest.raises(ValueError, match="Selesaikan"):
        pin_pipeline_sources(db_session, None, None, batch_id, None)
    assert (
        client.post(
            "/upload/batch-process", json={"pdpj_batch_id": batch_id}
        ).status_code
        == 422
    )
    review_id = start(client, batch_id)["id"]
    row = rows(client, review_id)[0]
    path = f"/pdpj/reviews/{review_id}/rows/{row['id']}"
    assert (
        client.patch(
            path,
            json=action(
                client, review_id, fields={"idpel": "001"}, reason="Koreksi identitas"
            ),
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/pdpj/reviews/{review_id}/complete", json=action(client, review_id)
        ).status_code
        == 200
    )
    later = upload(client, "prabayar", "IDPEL,LAT,LON\n003,-6.2,106.8\n")
    sources = pin_pipeline_sources(db_session, None, None, batch_id, None)
    assert (
        sources["dil"] == [master]
        and not sources["prabayar"]
        and sources["pdpj_review_id"] == review_id
    )
    with pytest.raises(ValueError, match="Sumber master berbeda"):
        pin_pipeline_sources(db_session, None, later, batch_id, None)
    process = ReconciliationProcess(
        process_name="validated PDPJ", source_batches=sources
    )
    db_session.add(process)
    db_session.commit()
    result = execute_pipeline(db_session, process.id)
    assert [
        item.idpel
        for item in db_session.query(MasterSisaRecord)
        .filter(MasterSisaRecord.snapshot_id == result["master_snapshot_id"])
        .all()
    ] == ["002"]
    start(client, batch_id)
    with pytest.raises(ValueError, match="Selesaikan"):
        pin_pipeline_sources(db_session, None, None, batch_id, None)
    assert (
        pin_pipeline_sources(
            db_session, None, None, batch_id, None, pdpj_review_id=review_id
        )["pdpj_review_id"]
        == review_id
    )


def test_validation_rejects_cross_review_rows_sources_and_invalid_inputs(
    client: TestClient,
) -> None:
    master = upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    batch_id = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    other_batch = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    review_id = start(client, batch_id)["id"]
    other = start(client, other_batch)["id"]
    row_id = rows(client, other)[0]["id"]
    path = f"/pdpj/reviews/{review_id}/rows/{row_id}"
    assert client.get(path).status_code == 404
    assert (
        client.patch(
            path, json=action(client, review_id, fields={"nama": "x"})
        ).status_code
        == 404
    )
    assert client.get(f"/pdpj/batches/{master}").status_code == 404
    assert client.get("/pdpj/batches/99999/reviews").status_code == 404
    assert client.get("/pdpj/reviews/99999").status_code == 404
    assert client.post("/pdpj/reviews", json={"batch_id": master}).status_code == 404
    assert (
        client.post(
            "/pdpj/reviews", json={"batch_id": batch_id, "master_batch_ids": []}
        ).status_code
        == 422
    )
    assert client.get(f"/pdpj/reviews/{review_id}/rows?limit=999").status_code == 422
    assert (
        client.post(
            f"/pdpj/reviews/{review_id}/complete", json={"revision": 1, "actor": " "}
        ).status_code
        == 422
    )
    own_id = rows(client, review_id)[0]["id"]
    assert (
        client.patch(
            f"/pdpj/reviews/{review_id}/rows/{own_id}",
            json=action(client, review_id, fields={"unknown": "x"}),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/pdpj/reviews/{review_id}/rows/{own_id}/apply",
            json=action(client, review_id, recommendation_id=99999, fields=["lat"]),
        ).status_code
        == 404
    )


def test_additive_migration_is_idempotent_and_reset_removes_review_dependencies(
    client: TestClient, db_session: Session
) -> None:
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    batch_id = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    review_id = start(client, batch_id)["id"]
    assert (
        client.post(
            f"/pdpj/reviews/{review_id}/complete", json=action(client, review_id)
        ).status_code
        == 200
    )
    with db_session.get_bind().begin() as connection:
        upgrade_pdpj_validation(connection)
        upgrade_pdpj_validation(connection)
        assert "pdpj_reviews" in inspect(connection).get_table_names()
    assert client.post("/upload/reset").status_code == 200
    for model in (PdpjReview, PdpjRow, PdpjRecommendation, PdpjChange):
        assert db_session.query(model).count() == 0
