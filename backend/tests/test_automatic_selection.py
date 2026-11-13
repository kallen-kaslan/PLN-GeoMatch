"""Distance competition, alternate candidates, immutable choices, and atomic export."""

import io

import pytest
from app.models.correction import CorrectionCandidateEvidence
from app.models.correction_decision import CorrectionDecision
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
    ReviewStatus,
)
from app.modules.corrections import automatic
from app.modules.corrections.automatic_candidates import candidate_frontier
from openpyxl import load_workbook

from tests.test_correction_map import body
from tests.test_corrections import check, upload
from tests.test_corrections import reference as reference  # noqa: PLC0414 -- Shared pytest fixture.


@pytest.fixture(params=["idpel_kosong", "idpel_tidak_ketemu"])
def scenario(client, db_session, reference, request):
    kind = request.param
    batch = upload(
        client,
        kind,
        "OBJECTID,IDPEL,NAMA,LAT,LON\n"
        + "".join(
            f"00{index},{'' if kind == 'idpel_kosong' else str(770 + index)},Target {index},-6.2,106.8\n"
            for index in range(1, 5)
        ),
    )
    checked = check(client, kind, batch, reference, radius=250)
    process = checked["process_id"]
    rows = client.get(
        f"/corrections/{kind}/records", params={"process_id": process}
    ).json()["items"]
    # A appears first but B is nearer to X. C must reach its third candidate.
    graph = [
        {"002": 12, "003": 18},
        {"002": 5, "004": 25},
        {"002": 30, "003": 35, "004": 40, "005": 45},
        {"006": 70},
    ]
    candidates = {}
    for row, distances in zip(rows, graph):
        for candidate in db_session.query(MatchCandidate).filter_by(
            process_id=process, target_record_id=row["id"]
        ):
            candidate.distance_meters = distances.get(candidate.candidate_idpel, 240)
            candidate.rank = (
                (
                    sorted(distances, key=distances.get).index(
                        candidate.candidate_idpel
                    )
                    + 1
                )
                if candidate.candidate_idpel in distances
                else 99
            )
            candidates[row["id"], candidate.candidate_idpel] = candidate.id
    db_session.commit()
    return kind, process, rows, candidates


def preview(client, scenario, radius=50):
    kind, process, _, _ = scenario
    response = client.post(
        f"/corrections/{kind}/checks/{process}/automatic/preview",
        json={"generation": 1, "radius_meters": radius},
    )
    assert response.status_code == 200, response.text
    return response.json()


def apply(client, scenario, plan, key="automatic_test_01"):
    kind, process, _, _ = scenario
    return client.post(
        f"/corrections/{kind}/checks/{process}/automatic/apply",
        json={
            "generation": plan["generation"],
            "radius_meters": plan["radius_meters"],
            "fingerprint": plan["fingerprint"],
            "request_key": key,
        },
    )


def choose(
    client, scenario, index, identity, key="manual_test_01", revision=0, reason=""
):
    kind, process, rows, candidates = scenario
    return client.post(
        f"/corrections/{kind}/checks/{process}/records/{rows[index]['id']}/choice",
        json=body(
            candidates[rows[index]["id"], identity] if identity else None,
            revision=revision,
            key=key,
            reason=reason,
        ),
    )


def test_global_distance_wins_over_row_order_and_uses_third_candidate(
    client, db_session, scenario
):
    kind, process, _rows, _candidates = scenario
    plan = preview(client, scenario)
    assert plan["selected_count"] == 3 and plan["fallback_count"] == 2
    assert plan["review_reasons"] == {"outside_radius": 1}
    assert db_session.query(CorrectionDecision).count() == 0
    result = apply(client, scenario, plan)
    assert result.status_code == 200, result.text
    events = (
        db_session.query(CorrectionDecision)
        .order_by(CorrectionDecision.target_record_id)
        .all()
    )
    assert [event.candidate["fields"]["idpel"] for event in events] == [
        "003",
        "002",
        "004",
    ]
    assert all(
        event.actor == "Petugas Uji" and "otomatis" in event.reason for event in events
    )
    assert (
        sum(candidate.is_accepted for candidate in db_session.query(MatchCandidate))
        == 3
    )
    assert apply(client, scenario, plan).json()["already_applied"] is True
    assert db_session.query(CorrectionDecision).count() == 3
    assert apply(client, scenario, plan, key="automatic_other_01").status_code == 409
    book = load_workbook(
        io.BytesIO(
            client.get(
                f"/corrections/{kind}/checks/{process}/results/export",
                params={"radius_meters": 50},
            ).content
        )
    )
    assert book.sheetnames == ["Hasil Koreksi"]
    exported = list(book.active.values)
    assert [row[0] for row in exported[1:]] == ["001", "002", "003"]
    assert [row[2] for row in exported[1:]] == ["003", "002", "004"]
    assert [row[-2:] for row in exported[1:]] == [(50, 18), (50, 5), (50, 40)]
    book.close()


def test_radius_filter_refreshes_summary_rows_paging_status_and_detail(
    client, db_session, scenario
):
    kind, process, rows, _candidates = scenario
    params = {"process_id": process, "radius_meters": 10}
    summary = client.get(f"/corrections/{kind}/summary", params=params).json()
    assert summary["matched"] == 1 and summary["no_candidates"] == 3
    filtered = client.get(f"/corrections/{kind}/records", params=params).json()
    assert filtered["total"] == 4
    assert [row["candidate_count"] for row in filtered["items"]] == [0, 1, 0, 0]
    assert [row["search_status"] for row in filtered["items"]] == [
        "no_candidates",
        "matched",
        "no_candidates",
        "no_candidates",
    ]
    selected = client.get(
        f"/corrections/{kind}/records",
        params={**params, "status": "matched", "limit": 1},
    ).json()
    assert selected["total"] == 1 and selected["items"][0]["id"] == rows[1]["id"]
    missing = client.get(
        f"/corrections/{kind}/records",
        params={**params, "status": "no_candidates", "skip": 1, "limit": 1},
    ).json()
    assert missing["total"] == 3 and missing["items"][0]["id"] == rows[2]["id"]
    detail = client.get(
        f"/corrections/{kind}/records/{rows[0]['id']}", params=params
    ).json()
    assert detail["radius_meters"] == 250 and detail["filter_radius_meters"] == 10
    assert detail["candidate_count"] == detail["candidates_total"] == 0
    assert detail["search_status"] == "no_candidates"
    wider = client.get(
        f"/corrections/{kind}/summary", params={**params, "radius_meters": 50}
    ).json()
    assert wider["matched"] == 3 and wider["no_candidates"] == 1
    full = client.get(
        f"/corrections/{kind}/summary", params={"process_id": process}
    ).json()
    assert full["matched"] == 4
    for endpoint in ("summary", "records"):
        assert (
            client.get(
                f"/corrections/{kind}/{endpoint}",
                params={**params, "radius_meters": 251},
            ).status_code
            == 409
        )
        assert (
            client.get(
                f"/corrections/{kind}/{endpoint}", params={"radius_meters": 10}
            ).status_code
            == 409
        )
    assert db_session.query(CorrectionDecision).count() == 0


def test_manual_choice_reserved_and_duplicate_manual_rejected_then_released(
    client, db_session, scenario
):
    assert choose(client, scenario, 0, "002").status_code == 200
    assert choose(client, scenario, 1, "002", key="duplicate_manual").status_code == 409
    plan = preview(client, scenario)
    assert plan["protected_count"] == 1 and plan["selected_count"] == 2
    assert apply(client, scenario, plan).status_code == 200
    choices = (
        db_session.query(CorrectionDecision)
        .order_by(CorrectionDecision.target_record_id)
        .all()
    )
    assert [item.candidate["fields"]["idpel"] for item in choices] == [
        "002",
        "004",
        "003",
    ]
    assert choices[0].reason == ""
    assert (
        choose(
            client,
            scenario,
            0,
            None,
            key="cancel_manual_01",
            revision=1,
            reason="Bebaskan IDPEL",
        ).status_code
        == 200
    )
    assert (
        choose(
            client,
            scenario,
            1,
            "002",
            key="replace_manual_01",
            revision=1,
            reason="Pilih yang lebih dekat",
        ).status_code
        == 200
    )
    assert preview(client, scenario)["protected_count"] == 3


def test_stale_preview_rejected_without_partial_writes(client, db_session, scenario):
    plan = preview(client, scenario)
    assert choose(client, scenario, 0, "003").status_code == 200
    result = apply(client, scenario, plan)
    assert result.status_code == 409
    assert db_session.query(CorrectionDecision).count() == 1


def test_equal_distance_across_targets_reserves_identity_for_review(
    client, db_session, scenario
):
    _, process, rows, candidates = scenario
    db_session.query(MatchCandidate).filter_by(process_id=process).update(
        {"distance_meters": 240}
    )
    for index in (0, 1, 2):
        candidate = db_session.get(MatchCandidate, candidates[rows[index]["id"], "002"])
        candidate.distance_meters = 5 if index < 2 else 6
    db_session.commit()
    plan = preview(client, scenario)
    assert plan["selected_count"] == 0
    assert plan["review_reasons"] == {
        "equal_distance": 2,
        "candidates_used": 1,
        "outside_radius": 1,
    }
    assert apply(client, scenario, plan).status_code == 200
    assert db_session.query(CorrectionDecision).count() == 0


def test_equal_candidates_on_one_target_require_review(client, db_session, scenario):
    _, process, rows, candidates = scenario
    db_session.query(MatchCandidate).filter_by(process_id=process).update(
        {"distance_meters": 240}
    )
    for identity in ("002", "003"):
        db_session.get(
            MatchCandidate, candidates[rows[0]["id"], identity]
        ).distance_meters = 5
    db_session.commit()
    plan = preview(client, scenario)
    assert plan["selected_count"] == 0
    assert plan["review_reasons"] == {"equal_distance": 1, "outside_radius": 3}


def test_radius_and_run_state_validated(client, db_session, scenario):
    kind, process, _, _ = scenario
    path = f"/corrections/{kind}/checks/{process}/automatic/preview"
    for radius in (0, -1, 251, "NaN"):
        assert (
            client.post(
                path, json={"generation": 1, "radius_meters": radius}
            ).status_code
            == 422
        )
    assert (
        client.post(
            path.replace(
                kind, "idpel_tidak_ketemu" if kind == "idpel_kosong" else "idpel_kosong"
            ),
            json={"generation": 1, "radius_meters": 50},
        ).status_code
        == 404
    )
    run = db_session.query(MatchingRun).filter_by(process_id=process).one()
    run.status = ProcessStatus.RUNNING
    db_session.commit()
    assert (
        client.post(path, json={"generation": 1, "radius_meters": 50}).status_code
        == 409
    )
    run.status = ProcessStatus.COMPLETED
    db_session.get(
        ReconciliationProcess, process
    ).review_status = ReviewStatus.FINALIZED
    db_session.commit()
    assert (
        client.post(path, json={"generation": 1, "radius_meters": 50}).status_code
        == 409
    )


def test_missing_evidence_rolls_back_all_selection(client, db_session, scenario):
    _, _, rows, candidates = scenario
    plan = preview(client, scenario)
    db_session.query(CorrectionCandidateEvidence).filter_by(
        candidate_id=candidates[rows[1]["id"], "002"]
    ).delete()
    db_session.commit()
    result = apply(client, scenario, plan)
    assert result.status_code == 409
    assert db_session.query(CorrectionDecision).count() == 0
    assert not db_session.query(MatchCandidate).filter_by(is_accepted=1).count()


def test_failure_after_insert_rolls_back_and_same_request_can_retry(
    client, db_session, scenario, monkeypatch
):
    plan = preview(client, scenario)
    insert = db_session.bulk_insert_mappings

    def failing_insert(model, values):
        insert(model, values[:1])
        raise RuntimeError("simulated interruption after first insert")

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "bulk_insert_mappings", failing_insert)
        with pytest.raises(RuntimeError, match="simulated interruption"):
            apply(client, scenario, plan)
    assert db_session.query(CorrectionDecision).count() == 0
    assert not db_session.query(MatchCandidate).filter_by(is_accepted=1).count()
    assert apply(client, scenario, plan).status_code == 200
    assert db_session.query(CorrectionDecision).count() == 3


def test_change_between_planning_and_writer_lock_is_rejected(
    client, db_session, scenario, monkeypatch
):
    plan = preview(client, scenario)
    real_lock = automatic.lock_review_session

    def changed(db):
        real_lock(db)
        monkeypatch.setattr(automatic, "decision_version", lambda *_: 999999)

    monkeypatch.setattr(automatic, "lock_review_session", changed)
    assert apply(client, scenario, plan).status_code == 409
    assert db_session.query(CorrectionDecision).count() == 0


def test_frontier_reads_beyond_first_page_and_stops_at_radius(db_session, scenario):
    _, process, rows, candidates = scenario
    record = rows[0]["id"]
    db_session.query(MatchCandidate).filter_by(
        process_id=process, target_record_id=record
    ).update({"rank": 99, "distance_meters": 240})
    template = db_session.get(MatchCandidate, candidates[record, "002"])
    for index in range(1, 35):
        db_session.add(
            MatchCandidate(
                process_id=process,
                generation=1,
                target_record_id=record,
                target_ref=template.target_ref,
                target_lat=template.target_lat,
                target_lon=template.target_lon,
                candidate_idpel=f"100{index:03}",
                candidate_lat=template.candidate_lat,
                candidate_lon=template.candidate_lon,
                distance_meters=index,
                rank=index,
            )
        )
    db_session.commit()
    run = db_session.query(MatchingRun).filter_by(process_id=process).one()
    pairs = list(
        candidate_frontier(
            db_session, run, 25, {row["id"] for row in rows[1:]}, {}, set()
        )
    )
    assert [pair.distance_meters for pair in pairs] == list(range(1, 26))
    assert len({pair.candidate_idpel for pair in pairs}) == 25


def test_old_duplicate_choices_require_review_without_rewriting_history(
    client, db_session, scenario
):
    _, process, rows, candidates = scenario
    assert choose(client, scenario, 0, "002").status_code == 200
    original = db_session.query(CorrectionDecision).one()
    duplicate = CorrectionDecision(
        process_id=process,
        target_record_id=rows[1]["id"],
        generation=1,
        revision=1,
        candidate_id=candidates[rows[1]["id"], "002"],
        request_key="legacy_duplicate_01",
        actor="Operator lama",
        reason="Pilihan sebelum aturan unik",
        target_fields={},
        candidate=original.candidate,
    )
    db_session.add(duplicate)
    db_session.commit()
    kind = scenario[0]
    result = client.post(
        f"/corrections/{kind}/checks/{process}/automatic/preview",
        json={"generation": 1, "radius_meters": 50},
    )
    assert result.status_code == 409 and "Peta Koreksi" in result.json()["detail"]
    assert db_session.query(CorrectionDecision).count() == 2


def test_manual_choice_from_previous_generation_stays_reserved(
    client, db_session, scenario
):
    kind, process, rows, _candidates = scenario
    assert choose(client, scenario, 0, "002").status_code == 200
    old_run = db_session.query(MatchingRun).filter_by(process_id=process).one()
    retried = client.post(
        f"/corrections/{kind}/checks/{process}/retry",
        json={
            "latest_run_id": old_run.id,
            "radius_meters": 250,
            "actor": "Petugas Uji",
            "request_key": "generation_retry_01",
        },
    )
    assert retried.status_code == 200 and retried.json()["current_generation"] == 2
    result = client.post(
        f"/corrections/{kind}/checks/{process}/automatic/preview",
        json={"generation": 2, "radius_meters": 50},
    )
    assert result.status_code == 200, result.text
    plan = result.json()
    assert plan["protected_count"] == 1
    assert apply(client, scenario, plan).status_code == 200
    candidate = (
        db_session.query(MatchCandidate)
        .filter_by(
            process_id=process,
            generation=2,
            target_record_id=rows[1]["id"],
            candidate_idpel="002",
        )
        .one()
    )
    duplicate = client.post(
        f"/corrections/{kind}/checks/{process}/records/{rows[1]['id']}/choice",
        json=body(candidate.id, generation=2, key="duplicate_new_generation"),
    )
    assert duplicate.status_code == 409
    assert (
        db_session.query(CorrectionDecision)
        .filter_by(target_record_id=rows[0]["id"])
        .count()
        == 1
    )
