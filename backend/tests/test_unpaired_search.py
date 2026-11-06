"""Radius follow-up reserves all prior pairs and never writes candidates or decisions."""

from io import BytesIO
from unittest.mock import Mock

import pytest
from app.config import settings
from app.models.correction_decision import CorrectionDecision
from app.models.matching import MatchCandidate, MatchingRun
from app.modules.corrections import router
from openpyxl import load_workbook

from tests.test_correction_map import body
from tests.test_corrections import check, upload


@pytest.fixture(
    params=[
        (kind, incremental)
        for kind in ("idpel_kosong", "idpel_tidak_ketemu")
        for incremental in (False, True)
    ]
)
def follow_up(client, db_session, monkeypatch, request):
    monkeypatch.setattr(settings, "ALLOW_SYNC_FALLBACK", True)
    monkeypatch.setattr(
        router.execute_batch_reconciliation_pipeline,
        "apply_async",
        Mock(side_effect=RuntimeError("offline")),
    )
    upload(
        client,
        "dil",
        "IDPEL,NAMA,LAT,LON,NOMOR_METER_KWH\n"
        "001,PDPJ,-6.2,106.8,M001\n"
        "002,A,-6.2,106.8,M002\n003,B,-6.2,106.8,M003\n"
        "006,Excluded,-6.2001,106.8,M006\n"
        "020,Tambahan A,-6.2005,106.8,M020\n"
        "021,Tambahan B,-6.201,106.8,M021\n"
        "030,Tambahan C,-6.208,106.8,M030\n"
        "040,Tanpa lokasi,,,M040\n",
    )
    pdpj = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n006,-6.2001,106.8\n")
    review = client.post("/pdpj/reviews", json={"batch_id": pdpj}).json()
    client.post(
        f"/pdpj/reviews/{review['id']}/complete",
        json={"revision": review["revision"], "actor": "Uji"},
    ).raise_for_status()
    kind, incremental = request.param
    batch = upload(
        client,
        kind,
        "OBJECTID,IDPEL,NAMA,LAT,LON,NOMOR_METER\n"
        + "".join(
            f"00{i},{'' if kind == 'idpel_kosong' else str(770 + i)},Target {i},-6.2,106.8,M020\n"
            for i in range(1, 6)
        ),
    )
    if incremental:
        response = client.post(
            f"/corrections/{kind}/checks",
            json={
                "batch_id": batch,
                "pdpj_review_id": review["id"],
                "radius_meters": 10,
                "request_key": "unpaired_all_observations",
                "actor": "Uji",
                "incremental": True,
            },
        )
        assert response.status_code == 200, response.text
        checked = response.json()
        run = checked["latest_run"]
        for _ in range(50):
            if run["status"] == "completed":
                break
            response = client.post(
                f"/corrections/{kind}/checks/{checked['process_id']}/advance",
                json={
                    "run_id": run["id"],
                    "revision": run["processing"]["revision"],
                    "chunk_size": 100,
                },
            )
            assert response.status_code == 200, response.text
            run = response.json()
        assert run["status"] == "completed"
    else:
        checked = check(client, kind, batch, review["id"], radius=10)
    base = f"/corrections/{kind}/checks/{checked['process_id']}"
    req = {"generation": 1, "radius_meters": 10, "tie_strategy": "suggest"}
    plan = client.post(base + "/automatic/preview", json=req).json()
    assert plan["suggestion_count"] == 2 and plan["unpaired_count"] == 3
    return (
        base,
        {**req, "fingerprint": plan["fingerprint"], "search_radius_meters": 500},
        plan,
        checked,
    )


def test_radius_scan_adds_unique_free_candidates_and_preserves_every_saved_search(
    client, db_session, follow_up
):
    base, req, plan, checked = follow_up
    before = db_session.query(MatchCandidate).count()
    # A new upload cannot participate in an old pinned examination.
    upload(client, "dil", "IDPEL,NAMA,LAT,LON\n007,Unpinned,-6.2,106.8\n")
    result = client.post(base + "/automatic/unpaired-search", json=req)
    assert result.status_code == 200, result.text
    data = result.json()
    assert (data["searched_count"], data["found_count"], data["unpaired_count"]) == (
        3,
        2,
        1,
    )
    candidates = [item["candidate"] for item in data["items"] if item["candidate"]]
    assert {item["idpel"] for item in candidates} == {"020", "021"}
    assert all(
        item["needs_verification"] and item["action"] == "expand_search"
        for item in candidates
    )
    assert all(item["source"]["filename"] == "dil.csv" for item in candidates)
    assert all(10 < item["distance_meters"] <= 500 for item in candidates)
    assert data["reason_counts"] == {"candidate_found": 2, "shared_candidates": 1}
    exported = client.post(base + "/automatic/unpaired-search/export", json=req)
    assert exported.status_code == 200, exported.text
    book = load_workbook(BytesIO(exported.content))
    assert book.sheetnames == ["Usulan Lanjutan"]
    values = list(book.active.values)
    assert {row[0] for row in values[1:]} == {"003", "004"}
    assert {row[2] for row in values[1:]} == {"020", "021"}
    assert all(
        row[10] == 500 and row[12] == "Perlu verifikasi" and row[14] == 10
        for row in values[1:]
    )
    assert book.active["L2"].number_format == '0.00" m"'
    book.close()
    wider = client.post(
        base + "/automatic/unpaired-search", json={**req, "search_radius_meters": 1000}
    ).json()
    assert wider["found_count"] == 3 and wider["unpaired_count"] == 0
    assert {item["candidate"]["idpel"] for item in wider["items"]} == {
        "020",
        "021",
        "030",
    }
    again = client.post(
        base + "/automatic/preview",
        json={k: req[k] for k in ("generation", "radius_meters", "tie_strategy")},
    ).json()
    assert again == plan
    assert db_session.query(MatchCandidate).count() == before
    assert db_session.query(CorrectionDecision).count() == 0
    assert db_session.get(MatchingRun, checked["latest_run"]["id"]).radius_meters == 10


def test_old_preview_rejected_after_verified_choice_and_locked_idpel_remains_excluded(
    client, db_session, follow_up
):
    base, req, plan, _ = follow_up
    item = plan["suggestions"][0]
    response = client.post(
        base + f"/records/{item['record_id']}/choice",
        json=body(
            item["candidate_id"], key="unpaired_lock_test", reason="Meter verified"
        ),
    )
    assert response.status_code == 200, response.text
    assert client.post(base + "/automatic/unpaired-search", json=req).status_code == 409
    plan2 = client.post(
        base + "/automatic/preview",
        json={k: req[k] for k in ("generation", "radius_meters", "tie_strategy")},
    ).json()
    response = client.post(
        base + "/automatic/unpaired-search",
        json={**req, "fingerprint": plan2["fingerprint"]},
    )
    assert response.status_code == 200, response.text
    assert item["idpel"] not in {
        row["candidate"]["idpel"]
        for row in response.json()["items"]
        if row["candidate"]
    }
    assert db_session.query(CorrectionDecision).count() == 1


def test_follow_up_scope_and_radius_limits(client, follow_up):
    base, req, _, _ = follow_up
    for override, expected in (
        ({"fingerprint": "0" * 64}, 409),
        ({"search_radius_meters": 10}, 422),
        ({"search_radius_meters": 5001}, 422),
        ({"generation": 999}, 409),
        ({"tie_strategy": "review"}, 422),
    ):
        response = client.post(
            base + "/automatic/unpaired-search", json={**req, **override}
        )
        assert response.status_code == expected, response.text
