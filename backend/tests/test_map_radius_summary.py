"""Radius summaries count targets, preserve blocked outcomes, and expose real changes."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.modules.corrections import map_summary as summary_module
from tests import test_corrections as corrections
from tests.test_corrections import check, upload

reference = corrections.reference


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_radius_summary_filters_saved_candidates_and_compares_incremental_expansion(
    client: TestClient,
    db_session: Session,
    reference: int,
    kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = "" if kind == "idpel_kosong" else "999"
    batch = upload(
        client,
        kind,
        "IDPEL,ID_TITIK,NAMA,LAT,LON\n"
        f"{identity},NEAR,Dekat,-6.2,106.8\n"
        f"{identity},OUTER,Baru pada 150,-6.2,106.8011\n"
        f"{identity},FAR,Jauh,-6.2,106.81\n"
        f"{identity},EMPTY,Kosong,,\n"
        f"{identity},S001,Benturan,-6.2,106.8\n"
        f"{identity},BAD,Rusak,bad,106.8\n",
    )
    started = check(client, kind, batch, reference, radius=100)
    process = started["process_id"]
    base = f"/corrections/{kind}"
    endpoint = base + "/map-summary"
    params = {"process_id": process, "generation": 1, "radius_meters": 100}
    statements: list[str] = []

    def capture(
        _conn: Any, _cursor: Any, sql: str, _params: Any, _context: Any, _many: bool
    ) -> None:
        statements.append(sql.lower())

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        response = client.get(endpoint, params=params)
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)
    assert response.status_code == 200
    original = response.json()
    assert original["total_rows"] == original["saved_rows"] == 6
    assert original["matched"] == 1 and original["no_candidates"] == 2
    assert original["candidate_total"] == 8 and len(original["candidate_counts"]) == 1
    assert original["not_checked"] == 0 and original["newly_matched"] == 0
    assert (
        original["pdpj_conflicts"]
        == original["invalid_data"]
        == original["incomplete_coordinates"]
        == 1
    )
    assert not any(
        forbidden in sql
        for sql in statements
        for forbidden in (
            "source_records",
            "master_sisa_records",
            "correction_candidate_evidence",
            "insert ",
            "update ",
            "delete ",
        )
    )
    narrow = client.get(endpoint, params={**params, "radius_meters": 1}).json()
    assert narrow["matched"] == 1 and narrow["candidate_total"] == 7
    assert narrow["no_candidates"] == 2 and narrow["baseline"]["radius_meters"] == 100
    assert (
        client.get(endpoint, params={**params, "radius_meters": 101}).status_code == 409
    )
    other = "idpel_kosong" if kind == "idpel_tidak_ketemu" else "idpel_tidak_ketemu"
    assert (
        client.get(f"/corrections/{other}/map-summary", params=params).status_code
        == 404
    )
    assert client.get(endpoint, params={**params, "generation": 99}).status_code == 404
    for invalid in (0, -1, "nan", "inf", 100001):
        assert (
            client.get(
                endpoint, params={**params, "radius_meters": invalid}
            ).status_code
            == 422
        )
    retry = client.post(
        base + f"/checks/{process}/retry",
        json={
            "latest_run_id": started["latest_run"]["id"],
            "radius_meters": 150,
            "actor": "Petugas",
            "request_key": "radius_summary_expand",
            "incremental": True,
        },
    ).json()
    expanded_params = {**params, "generation": 2, "radius_meters": 150}
    empty = client.get(endpoint, params=expanded_params).json()
    assert empty["saved_rows"] == empty["no_candidates"] == 0
    assert empty["not_checked"] == 6 and empty["partial"]
    run = retry["latest_run"]
    saved_snapshot = None
    while run["status"] != "completed":
        response = client.post(
            base + f"/checks/{process}/advance",
            json={
                "run_id": run["id"],
                "revision": run["processing"]["revision"],
                "chunk_size": 1,
            },
        )
        assert response.status_code == 200, response.text
        run = response.json()
        if run["processing"]["processed_rows"] == 2:
            saved_snapshot = dict(run)
            partial = client.get(endpoint, params=expanded_params).json()
            assert partial["saved_rows"] == partial["matched"] == 2
            assert partial["not_checked"] == 4 and partial["no_candidates"] == 0
            assert partial["newly_matched"] == 1
            assert partial["baseline"]["no_candidates"] == 2
    final = client.get(endpoint, params=expanded_params).json()
    assert final["matched"] == 2 and final["no_candidates"] == 1
    assert final["newly_matched"] == 1 and not final["partial"]
    assert final["candidate_total"] == 16
    assert saved_snapshot is not None
    with monkeypatch.context() as patch:
        patch.setattr(
            summary_module,
            "selected_run",
            lambda *_args, **_kwargs: SimpleNamespace(**saved_snapshot),
        )
        consistent = client.get(endpoint, params=expanded_params).json()
        assert consistent["saved_rows"] == consistent["matched"] == 2
        assert consistent["not_checked"] == 4 and consistent["no_candidates"] == 0
    assert client.get(endpoint, params=params).json() == original
    smaller = client.get(
        endpoint, params={**expanded_params, "radius_meters": 1}
    ).json()
    assert smaller["matched"] == 1 and smaller["no_candidates"] == 2
    assert smaller["baseline"]["generation"] == 2
