"""Suggestion matching is unique, distance-first, read-only, and explicitly unverified."""

import io

from app.models.correction_decision import CorrectionDecision
from app.models.matching import MatchCandidate
from app.modules.corrections.tie_suggestions import equal_distance_matching
from openpyxl import load_workbook

from tests.test_automatic_selection import scenario as scenario  # noqa: PLC0414 -- Shared fixture.
from tests.test_corrections import reference as reference  # noqa: PLC0414 -- Shared fixture dependency.


def setup(db, scenario):
    _, process, rows, candidates = scenario
    db.query(MatchCandidate).filter_by(process_id=process).update(
        {"distance_meters": 240, "rank": 99}
    )
    for index, values in enumerate(({"002": 5, "003": 5}, {"002": 5}, {"006": 2}, {})):
        for rank, (identity, distance) in enumerate(values.items(), 1):
            candidate = db.get(MatchCandidate, candidates[rows[index]["id"], identity])
            candidate.distance_meters, candidate.rank = distance, rank
    db.commit()


def request(client, scenario, strategy="suggest"):
    kind, process, _, _ = scenario
    return client.post(
        f"/corrections/{kind}/checks/{process}/automatic/preview",
        json={"generation": 1, "radius_meters": 50, "tie_strategy": strategy},
    )


def test_tie_mode_proposes_unique_pairs_without_saving_and_exports_separate_sheet(
    client, db_session, scenario
):
    setup(db_session, scenario)
    kind, process, rows, _ = scenario
    normal = request(client, scenario, "review").json()
    proposed = request(client, scenario).json()
    assert normal["selected_count"] == proposed["selected_count"] == 1
    assert proposed["suggestion_count"] == 2 and proposed["unpaired_count"] == 1
    assert [(item["record_id"], item["idpel"]) for item in proposed["suggestions"]] == [
        (rows[0]["id"], "003"),
        (rows[1]["id"], "002"),
    ]
    assert all(item["needs_verification"] for item in proposed["suggestions"])
    assert proposed["fingerprint"] != normal["fingerprint"]
    assert db_session.query(CorrectionDecision).count() == 0
    assert not db_session.query(MatchCandidate).filter_by(is_accepted=1).count()
    exported = client.post(
        f"/corrections/{kind}/checks/{process}/automatic/suggestions/export",
        json={
            "generation": 1,
            "radius_meters": 50,
            "fingerprint": proposed["fingerprint"],
        },
    )
    assert exported.status_code == 200, exported.text
    book = load_workbook(io.BytesIO(exported.content))
    assert book.sheetnames == ["Usulan Jarak Sama"]
    values = list(book.active.values)
    assert values[0][-2:] == ("Status Usulan", "Baris Target")
    assert [(row[0], row[2], row[-2], row[-1]) for row in values[1:]] == [
        ("001", "003", "Perlu verifikasi", 2),
        ("002", "002", "Perlu verifikasi", 3),
    ]
    assert book.active["L2"].number_format == '0.00" m"'
    book.close()
    assert db_session.query(CorrectionDecision).count() == 0
    apply_body = {
        "generation": 1,
        "radius_meters": 50,
        "fingerprint": proposed["fingerprint"],
        "request_key": "suggestion_apply_01",
    }
    assert (
        client.post(
            f"/corrections/{kind}/checks/{process}/automatic/apply", json=apply_body
        ).status_code
        == 409
    )
    applied = client.post(
        f"/corrections/{kind}/checks/{process}/automatic/apply",
        json={**apply_body, "tie_strategy": "suggest"},
    )
    assert applied.status_code == 200, applied.text
    saved = db_session.query(CorrectionDecision).one()
    assert (
        saved.target_record_id == rows[2]["id"]
        and saved.candidate["fields"]["idpel"] == "006"
    )
    assert (
        client.post(
            f"/corrections/{kind}/checks/{process}/automatic/suggestions/export",
            json={
                "generation": 1,
                "radius_meters": 50,
                "fingerprint": proposed["fingerprint"],
            },
        ).status_code
        == 409
    )


def test_tie_mode_continues_to_alternatives_and_nearer_distance_keeps_priority(
    client, db_session, scenario
):
    setup(db_session, scenario)
    _, process, rows, candidates = scenario
    # C is closer to X than either tied target. A/B must use other identities.
    db_session.query(MatchCandidate).filter_by(
        process_id=process, target_record_id=rows[2]["id"]
    ).update({"distance_meters": 240, "rank": 99})
    candidate = db_session.get(MatchCandidate, candidates[rows[2]["id"], "002"])
    candidate.distance_meters, candidate.rank = 1, 1
    extra = db_session.get(MatchCandidate, candidates[rows[1]["id"], "004"])
    extra.distance_meters, extra.rank = 8, 2
    db_session.commit()
    data = request(client, scenario).json()
    identities = [item["idpel"] for item in data.get("suggestions", [])]
    assert "002" not in identities
    assert data["selected_count"] >= 1
    assert data["suggestion_count"] == 0  # Existing strict choices already cover A/B/C.
    assert db_session.query(CorrectionDecision).count() == 0


def test_matching_uses_augmenting_paths_without_recursion():
    graph = {
        index: {f"ID{index:05}": True, f"ID{index + 1:05}": True}
        for index in range(1500)
    }
    graph[1500] = {"ID00000": True}
    chosen = equal_distance_matching(graph)
    assert len(chosen) == len(set(chosen.values())) == 1501
    assert all(identity in graph[record] for record, identity in chosen.items())


def test_matching_cardinality_on_all_small_graphs():
    for mask in range(512):
        graph = {
            record: {
                str(identity): True
                for identity in range(3)
                if mask & (1 << (record * 3 + identity))
            }
            for record in range(3)
        }
        chosen = equal_distance_matching(graph)

        def brute(record, used, edges=graph):
            if record == 3:
                return 0
            return max(
                [
                    brute(record + 1, used),
                    *(
                        1 + brute(record + 1, used | {identity})
                        for identity in edges[record]
                        if identity not in used
                    ),
                ]
            )

        assert len(chosen) == brute(0, set())
