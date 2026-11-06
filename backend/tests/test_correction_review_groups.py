"""Review shared coordinates/identities without weakening exclusive audited choices."""

from app.models.correction_decision import CorrectionDecision
from app.models.matching import MatchCandidate

from tests.test_automatic_selection import choose, preview
from tests.test_automatic_selection import scenario as scenario  # noqa: PLC0414 -- Shared parametrized fixture.
from tests.test_corrections import reference as reference  # noqa: PLC0414 -- Shared fixture dependency.


def configure_ties(db, scenario):
    _, process, rows, candidates = scenario
    db.query(MatchCandidate).filter_by(process_id=process).update(
        {"distance_meters": 240, "rank": 99}
    )
    for index, values in enumerate(
        ({"002": 5, "003": 5}, {"002": 6, "003": 6}, {"002": 7}, {})
    ):
        for rank, (identity, distance) in enumerate(values.items(), 1):
            candidate = db.get(MatchCandidate, candidates[rows[index]["id"], identity])
            candidate.distance_meters, candidate.rank = distance, rank
    db.commit()


def groups(client, scenario, plan):
    kind, process, _, _ = scenario
    return client.post(
        f"/corrections/{kind}/checks/{process}/automatic/review-groups",
        json={
            "generation": plan["generation"],
            "radius_meters": plan["radius_meters"],
            "fingerprint": plan["fingerprint"],
        },
    )


def test_group_compares_shared_coordinates_and_recalculates_after_verified_choice(
    client, db_session, scenario
):
    configure_ties(db_session, scenario)
    kind, process, rows, _ = scenario
    plan = preview(client, scenario)
    assert plan["review_reasons"] == {
        "equal_distance": 1,
        "candidates_used": 2,
        "outside_radius": 1,
    }
    response = groups(client, scenario, plan)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["group_count"] == 2 and data["target_count"] == 4
    shared = data["groups"][0]
    assert shared["target_count"] == 3 and shared["candidate_count"] == 2
    assert len(shared["coordinates"]) == 1
    assert [item["record_id"] for item in shared["targets"]] == [
        row["id"] for row in rows[:3]
    ]
    assert db_session.query(CorrectionDecision).count() == 0
    assert (
        choose(
            client, scenario, 0, "002", reason="Nomor meter cocok dengan bukti lapangan"
        ).status_code
        == 200
    )
    assert groups(client, scenario, plan).status_code == 409
    updated = preview(client, scenario)
    assert updated["selected_count"] == 1 and updated["protected_count"] == 1
    assert updated["review_count"] == 2
    remaining = groups(client, scenario, updated).json()
    locked_group = next(
        group
        for group in remaining["groups"]
        if any(target["record_id"] == rows[2]["id"] for target in group["targets"])
    )
    assert locked_group["candidates"][0]["used_by"] == [
        {"record_id": rows[0]["id"], "row_number": 2}
    ]
    detail = client.get(
        f"/corrections/{kind}/records/{rows[2]['id']}",
        params={
            "process_id": process,
            "generation": 1,
            "radius_meters": 50,
            "include_usage": True,
        },
    ).json()
    locked = next(
        item for item in detail["candidates"] if item["fields"]["idpel"] == "002"
    )
    assert locked["used_by"] == [{"record_id": rows[0]["id"], "row_number": 2}]
    assert (
        choose(client, scenario, 2, "002", key="review_cannot_reuse").status_code == 409
    )
    event = db_session.query(CorrectionDecision).one()
    assert event.reason == "Nomor meter cocok dengan bukti lapangan"


def test_coordinate_groups_keep_original_precision(client, db_session, scenario):
    _, process, rows, candidates = scenario
    db_session.query(MatchCandidate).filter_by(process_id=process).update(
        {"distance_meters": 240, "rank": 99}
    )
    for index, identities in enumerate((("002", "003"), ("004", "005"))):
        for rank, identity in enumerate(identities, 1):
            candidate = db_session.get(
                MatchCandidate, candidates[rows[index]["id"], identity]
            )
            candidate.distance_meters, candidate.rank = 5 + index, rank
            candidate.candidate_lat = -6.200000001 - index * 0.000000001
    db_session.commit()
    data = groups(client, scenario, preview(client, scenario)).json()
    tied = [
        group for group in data["groups"] if "equal_distance" in group["reason_counts"]
    ]
    assert len(tied) == 2
    assert all(
        group["target_count"] == 1 and group["candidate_count"] == 2 for group in tied
    )
    assert tied[0]["coordinates"] != tied[1]["coordinates"]


def test_shared_idpel_connects_different_observation_coordinates(
    client, db_session, scenario
):
    _, process, rows, candidates = scenario
    db_session.query(MatchCandidate).filter_by(process_id=process).update(
        {"distance_meters": 240, "rank": 99}
    )
    for index in (0, 1):
        candidate = db_session.get(MatchCandidate, candidates[rows[index]["id"], "002"])
        candidate.distance_meters, candidate.rank = 5, 1
        candidate.candidate_lat = -6.201 - index * 0.001
    db_session.commit()
    data = groups(client, scenario, preview(client, scenario)).json()
    tied = next(
        group for group in data["groups"] if "equal_distance" in group["reason_counts"]
    )
    assert tied["target_count"] == 2 and tied["candidate_count"] == 1
    assert len(tied["coordinates"]) == 2
    assert (
        len(
            {item["record_id"] for group in data["groups"] for item in group["targets"]}
        )
        == data["target_count"]
    )
