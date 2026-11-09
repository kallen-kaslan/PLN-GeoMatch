"""Complete automatic selection publishes unique pairs and an immutable radius version."""

from io import BytesIO

import pytest
from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.correction_decision import CorrectionDecision
from app.models.matching import MatchCandidate, MatchingRun
from openpyxl import load_workbook

from tests.test_correction_map import body
from tests.test_corrections import check, upload
from tests.test_unpaired_search import follow_up as follow_up  # noqa: PLC0414 -- Shared scenario.


def preview(client, follow_up, maximum=500):
    base, _, _, _ = follow_up
    params = {"generation": 1, "radius_meters": 10, "max_radius_meters": maximum}
    response = client.post(base + "/automatic/complete/preview", json=params)
    assert response.status_code == 200, response.text
    return response.json(), params


def apply(client, follow_up, plan, params, key="complete_selection_test_01"):
    return client.post(
        follow_up[0] + "/automatic/complete/apply",
        json={**params, "fingerprint": plan["fingerprint"], "request_key": key},
    )


def test_complete_saves_ties_and_extensions_and_preserves_history_and_map(
    client, db_session, follow_up
):
    base, _, _, checked = follow_up
    old_candidates = db_session.query(MatchCandidate).count()
    plan, req = preview(client, follow_up, 1000)
    assert plan["selected_count"] == 5
    assert (
        plan["equal_distance_count"],
        plan["expanded_count"],
        plan["unpaired_count"],
    ) == (2, 3, 0)
    assert plan["creates_version"] and plan["result_radius_meters"] == 1000
    assert db_session.query(MatchingRun).count() == 1
    saved = apply(client, follow_up, plan, req)
    assert saved.status_code == 200, saved.text
    assert saved.json()["generation"] == 2 and saved.json()["selected_count"] == 5
    assert db_session.query(MatchCandidate).count() == old_candidates + 3
    assert db_session.query(CorrectionTarget).count() == 10
    assert db_session.query(CorrectionDecision).count() == 5
    events = db_session.query(CorrectionDecision).all()
    assert len({event.candidate["fields"]["idpel"] for event in events}) == 5
    assert all(
        not event.candidate["automatic_selection"]["identity_verified"]
        for event in events
    )
    assert {event.candidate["automatic_selection"]["method"] for event in events} == {
        "equal_distance",
        "expanded_radius",
    }
    current = client.get(base + "/results", params={"generation": 2}).json()
    historical = client.get(base + "/results", params={"generation": 1}).json()
    assert (
        current["summary"]["chosen_count"] == current["summary"]["total_targets"] == 5
    )
    assert historical["summary"]["chosen_count"] == 0
    assert historical["summary"]["radius_meters"] == 10
    assert (
        len(
            client.get(
                base + "/results",
                params={"generation": 2, "radius_meters": 10, "status": "selected"},
            ).json()["items"]
        )
        == 2
    )
    for row in current["items"]:
        details = client.get(
            base.split("/checks")[0] + f"/records/{row['record_id']}",
            params={
                "process_id": checked["process_id"],
                "generation": 2,
                "radius_meters": 1000,
                "include_usage": True,
            },
        )
        assert details.status_code == 200, details.text
        assert (
            len(details.json()["candidates"]) >= 2
        )  # Earlier alternatives remain usable.
        assert row["choice"]["candidate_id"] in {
            candidate["id"] for candidate in details.json()["candidates"]
        }
    exported = client.get(
        base + "/results/export",
        params={"generation": 2, "radius_meters": 1000, "status": "selected"},
    )
    assert exported.status_code == 200, exported.text
    book = load_workbook(BytesIO(exported.content))
    assert book.sheetnames == ["Hasil Koreksi"]
    values = list(book.active.values)
    assert len(values) == 6 and len(values[0]) == 12
    assert {row[2] for row in values[1:]} == {"002", "003", "020", "021", "030"}
    assert all(row[10] == 1000 for row in values[1:])
    assert book.active["L2"].number_format == '0.00" m"'
    replay = apply(client, follow_up, plan, req)
    assert replay.status_code == 200 and replay.json()["already_applied"]
    assert db_session.query(CorrectionDecision).count() == 5
    assert db_session.query(MatchingRun).count() == 2
    assert (
        client.post(
            base + "/automatic/complete/apply",
            json={
                **req,
                "fingerprint": "0" * 64,
                "request_key": "complete_selection_test_01",
            },
        ).status_code
        == 409
    )


def test_ties_can_be_saved_without_expansion_then_only_remaining_targets_expand(
    client, db_session, follow_up
):
    base = follow_up[0]
    plan, req = preview(client, follow_up, 10)
    assert plan["selected_count"] == 2 and plan["unpaired_count"] == 3
    assert not plan["creates_version"]
    response = apply(client, follow_up, plan, req)
    assert response.status_code == 200, response.text
    original = {
        event.target_record_id: event.id
        for event in db_session.query(CorrectionDecision)
    }
    wider, req = preview(client, follow_up, 1000)
    assert wider["protected_count"] == 2 and wider["selected_count"] == 3
    response = apply(client, follow_up, wider, req, key="complete_expand_02")
    assert response.status_code == 200, response.text
    assert db_session.query(CorrectionDecision).count() == 5
    assert all(
        db_session.query(CorrectionDecision).filter_by(target_record_id=record).one().id
        == event_id
        for record, event_id in original.items()
    )
    assert (
        client.get(base + "/results", params={"generation": 1}).json()["summary"][
            "chosen_count"
        ]
        == 2
    )
    # Existing alternatives can still be selected from the inherited generation.
    row = client.get(base + "/results").json()["items"][0]
    cancelled = client.post(
        base + f"/records/{row['record_id']}/choice",
        json=body(
            None,
            revision=1,
            generation=2,
            key="complete_cancel_03",
            reason="Periksa lapangan",
        ),
    )
    assert cancelled.status_code == 200, cancelled.text
    chosen = client.post(
        base + f"/records/{row['record_id']}/choice",
        json=body(
            row["choice"]["candidate_id"],
            revision=2,
            generation=2,
            key="complete_rechoose_04",
            reason="Sesuai meter",
        ),
    )
    assert chosen.status_code == 200, chosen.text


def test_stale_preview_and_failure_leave_no_partial_version_or_choices(
    client, db_session, follow_up, monkeypatch
):
    plan, req = preview(client, follow_up, 1000)
    old_candidates = db_session.query(MatchCandidate).count()
    old_evidence = db_session.query(CorrectionCandidateEvidence).count()
    with monkeypatch.context() as patch:

        def fail(*args, **kwargs):
            raise RuntimeError("simulated write failure")

        patch.setattr(db_session, "bulk_insert_mappings", fail)
        with pytest.raises(RuntimeError, match="simulated write failure"):
            apply(client, follow_up, plan, req)
    assert db_session.query(MatchingRun).count() == 1
    assert db_session.query(CorrectionDecision).count() == 0
    assert db_session.query(MatchCandidate).count() == old_candidates
    assert db_session.query(CorrectionCandidateEvidence).count() == old_evidence
    suggestion = follow_up[2]["suggestions"][0]
    response = client.post(
        follow_up[0] + f"/records/{suggestion['record_id']}/choice",
        json=body(suggestion["candidate_id"], key="complete_concurrent_choice"),
    )
    assert response.status_code == 200, response.text
    assert apply(client, follow_up, plan, req).status_code == 409
    assert db_session.query(MatchingRun).count() == 1


def test_extension_publishes_previously_empty_target_and_radius_summary(
    client, db_session, follow_up
):
    kind = follow_up[0].split("/")[2]
    batch = upload(
        client,
        kind,
        "OBJECTID,IDPEL,NAMA,LAT,LON\n"
        + (
            "900,,Tanpa kandidat,-6.2045,106.8\n"
            if kind == "idpel_kosong"
            else "900,999,Tanpa kandidat,-6.2045,106.8\n"
        ),
    )
    checked = check(
        client,
        kind,
        batch,
        follow_up[3]["pdpj_review_id"],
        key="complete_empty_target",
        radius=10,
    )
    base = f"/corrections/{kind}/checks/{checked['process_id']}"
    req = {"generation": 1, "radius_meters": 10, "max_radius_meters": 500}
    response = client.post(base + "/automatic/complete/preview", json=req)
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["expanded_count"] == 1 and plan["unpaired_count"] == 0
    response = client.post(
        base + "/automatic/complete/apply",
        json={
            **req,
            "fingerprint": plan["fingerprint"],
            "request_key": "complete_empty_save_01",
        },
    )
    assert response.status_code == 200, response.text
    summary = client.get(
        f"/corrections/{kind}/map-summary",
        params={
            "process_id": checked["process_id"],
            "generation": 2,
            "radius_meters": 500,
        },
    ).json()
    assert (
        summary["matched"]
        == summary["newly_matched"]
        == summary["candidate_total"]
        == 1
    )
    assert summary["no_candidates"] == 0
    assert (
        client.get(base + "/results", params={"generation": 1}).json()["summary"][
            "matched_targets"
        ]
        == 0
    )
