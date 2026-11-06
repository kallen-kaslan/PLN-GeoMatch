"""Identity lookup stays inside the pinned eligible snapshot and never mutates a run."""

from unittest.mock import Mock

import pytest
from app.config import settings
from app.models.correction_decision import CorrectionDecision
from app.models.matching import MatchCandidate
from app.models.upload import UploadBatch
from app.modules.corrections import advanced_search, router

from tests.test_correction_map import body
from tests.test_corrections import check, upload


@pytest.fixture(params=["idpel_kosong", "idpel_tidak_ketemu"])
def finder(client, db_session, monkeypatch, request):
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(side_effect=RuntimeError("offline")),
    )
    original = upload(
        client,
        "dil",
        "IDPEL,NAMA,LAT,LON,NOMOR_METER_KWH,ALAMAT,NOMOR_GARDU\n001,PDPJ,-6.2,106.8,M001,PDPJ,G0\n002,Andi,-6.2,106.8,M002,Jalan A,G1\n003,Andika,-6.2,106.8,M003,Jalan B,G1\n004,Jauh,-6.205,106.8,M004,Jalan C,G2\n005,Tanpa koordinat,,,M005,Jalan D,G2\n006,PDPJ excluded,-6.2,106.8,M006,Jalan E,G1\n",
    )
    upload(
        client,
        "pascabayar",
        "IDPEL,NAMA,LAT,LON,NOMOR_METER_KWH,TGLBACA\n002,Andi lama,-6.21,106.8,OLD002,2025-01-01\n",
    )
    pdpj = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n006,-6.2,106.8\n")
    review = client.post("/pdpj/reviews", json={"batch_id": pdpj}).json()
    client.post(
        f"/pdpj/reviews/{review['id']}/complete",
        json={"revision": review["revision"], "actor": "Petugas Uji"},
    ).raise_for_status()
    kind = request.param
    batch = upload(
        client,
        kind,
        "IDPEL,NAMA,LAT,LON,NOMOR_METER,ALAMAT\n"
        + "".join(
            f"{'' if kind == 'idpel_kosong' else str(770 + i)},Target {i},-6.20005,106.8,M002,Jalan A\n"
            for i in (1, 2)
        ),
    )
    checked = check(client, kind, batch, review["id"], radius=50)
    process = checked["process_id"]
    rows = client.get(
        f"/corrections/{kind}/records", params={"process_id": process}
    ).json()["items"]
    return {
        "kind": kind,
        "process": process,
        "rows": rows,
        "base": f"/corrections/{kind}/checks/{process}",
        "original": original,
        "run": checked["latest_run"]["id"],
    }


def search(client, finder, q, field="meter", index=0, **extra):
    return client.get(
        finder["base"] + f"/records/{finder['rows'][index]['id']}/advanced-candidates",
        params={"generation": 1, "radius_meters": 50, "field": field, "q": q, **extra},
    )


def test_search_finds_identity_evidence_and_retains_stored_coordinates(
    client, db_session, finder
):
    before = db_session.query(MatchCandidate).count()
    response = search(client, finder, "M002")
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["idpel"] == "002" and item["action"] == "choose"
    assert item["target_meter_matches"] is True
    assert "Nomor meter cocok dengan data target" in item["reasons"]
    assert "Alamat sama dengan data target" in item["reasons"]
    assert item["matched_sources"][0]["filename"] == "dil.csv"
    assert item["candidate"]["distance_meters"] == item["distance_meters"]
    legacy = search(client, finder, "OLD002").json()["items"][0]
    assert legacy["matched_sources"][0]["filename"] == "pascabayar.csv"
    assert legacy["coordinate_source"]["filename"] == "dil.csv"
    assert legacy["distance_meters"] == item["distance_meters"]
    assert legacy["candidate"]["id"] == item["candidate"]["id"]
    assert db_session.query(MatchCandidate).count() == before
    assert db_session.query(CorrectionDecision).count() == 0


def test_excludes_pdpj_used_idpel_and_new_uploads(client, finder):
    for q, field in (("006", "idpel"), ("M006", "meter")):
        assert search(client, finder, q, field).json()["items"] == []
    upload(
        client,
        "dil",
        "IDPEL,NAMA,LAT,LON,NOMOR_METER_KWH\n007,Outside snapshot,-6.2,106.8,M007\n",
    )
    assert search(client, finder, "M007").json()["items"] == []
    assert search(client, finder, "007", "idpel").json()["items"] == []
    candidate = search(client, finder, "002", "idpel").json()["items"][0]["candidate"]
    response = client.post(
        finder["base"] + f"/records/{finder['rows'][0]['id']}/choice",
        json=body(
            candidate["id"], key="advanced_choose_01", reason="Meter sesuai bukti"
        ),
    )
    assert response.status_code == 200, response.text
    assert search(client, finder, "M002", index=1).json()["items"] == []
    assert search(client, finder, "002", "idpel", index=1).json()["items"] == []


def test_outside_radius_and_missing_coordinates_need_explicit_follow_up(
    client, db_session, finder
):
    far = search(client, finder, "M004").json()["items"][0]
    assert far["action"] == "expand_search" and far["candidate"] is None
    assert far["distance_meters"] > 50
    assert far["suggested_radius_meters"] > far["distance_meters"]
    missing = search(client, finder, "005", "idpel").json()["items"][0]
    assert missing["action"] == "missing_coordinates" and missing["candidate"] is None
    assert missing["distance_meters"] is None
    smaller = search(client, finder, "M002", radius_meters=1).json()["items"][0]
    assert smaller["action"] == "change_filter" and smaller["candidate"] is None
    assert db_session.query(CorrectionDecision).count() == 0


def test_names_gardu_pagination_and_search_readiness(client, finder, monkeypatch):
    first = search(client, finder, "And", "nama", limit=1).json()
    assert len(first["items"]) == 1 and first["has_more"]
    second = search(client, finder, "And", "nama", limit=1, skip=1).json()
    assert (
        len(second["items"]) == 1
        and first["items"][0]["idpel"] != second["items"][0]["idpel"]
    )
    assert search(client, finder, "G1", "gardu").status_code == 422
    assert search(client, finder, "%%%", "nama").json()["items"] == []
    monkeypatch.setattr(
        advanced_search,
        "prepare_search",
        lambda *_: {"ready": False, "processed_rows": 123},
    )
    pending = search(client, finder, "M002").json()
    assert pending["search_index"] == {"ready": False, "processed_rows": 123}
    assert pending["items"] == []


def test_stale_generation_changed_mapping_and_scope_rejected(
    client, db_session, finder
):
    assert search(client, finder, "M002", radius_meters=51).status_code == 422
    assert search(client, finder, "   ").status_code == 422
    assert search(client, finder, "000").status_code == 422
    wrong = finder["base"].replace(
        finder["kind"],
        "idpel_tidak_ketemu" if finder["kind"] == "idpel_kosong" else "idpel_kosong",
    )
    assert (
        client.get(
            wrong + f"/records/{finder['rows'][0]['id']}/advanced-candidates",
            params={"generation": 1, "radius_meters": 50, "q": "M002"},
        ).status_code
        == 404
    )
    batch = db_session.get(UploadBatch, finder["original"])
    mapping = batch.column_mapping
    batch.column_mapping = {"idpel": "NAMA"}
    db_session.commit()
    assert search(client, finder, "M002").status_code == 409
    batch.column_mapping = mapping
    db_session.commit()
    response = client.post(
        finder["base"] + "/retry",
        json={
            "latest_run_id": finder["run"],
            "radius_meters": 100,
            "actor": "Petugas Uji",
            "request_key": "advanced_new_run_01",
            "incremental": True,
        },
    )
    assert response.status_code == 200
    assert search(client, finder, "M002").status_code == 409
