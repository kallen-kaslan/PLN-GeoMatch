"""Saved choices project immediately into partial results, history and export."""

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.upload import SourceRecord
from tests.test_correction_map import body
from tests.test_corrections import upload


@pytest.fixture(params=["idpel_kosong", "idpel_tidak_ketemu"])
def partial(client: TestClient, request: pytest.FixtureRequest) -> dict:
    kind = request.param
    upload(
        client,
        "dil",
        "IDPEL,NAMA,LAT,LON\n001,PDPJ,-6.2,106.8\n002,First,-6.2,106.8\n003,Second,-6.2,106.8\n",
    )
    pdpj = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    review = client.post("/pdpj/reviews", json={"batch_id": pdpj}).json()
    assert (
        client.post(
            f"/pdpj/reviews/{review['id']}/complete",
            json={"revision": review["revision"], "actor": "Petugas"},
        ).status_code
        == 200
    )
    batch = upload(
        client,
        kind,
        "IDPEL,NAMA,LAT,LON\n"
        + "".join(
            f"{700 + i if kind == 'idpel_tidak_ketemu' else ''},Target {i},-6.2,106.8\n"
            for i in range(5)
        ),
    )
    checked = client.post(
        f"/corrections/{kind}/checks",
        json={
            "batch_id": batch,
            "pdpj_review_id": review["id"],
            "radius_meters": 10,
            "actor": "Petugas",
            "request_key": "result_request_1",
            "incremental": True,
        },
    )
    assert checked.status_code == 200, checked.json()
    result = checked.json()
    result["kind"] = kind
    result["base"] = f"/corrections/{kind}/checks/{result['process_id']}"
    run = result["latest_run"]
    for _ in range(2):
        run = advance(client, result, run)
    result["latest_run"] = run
    rows = client.get(
        f"/corrections/{kind}/records", params={"process_id": result["process_id"]}
    ).json()["items"]
    result["record"] = rows[0]["id"]
    result["candidates"] = client.get(
        f"/corrections/{kind}/records/{result['record']}",
        params={"process_id": result["process_id"]},
    ).json()["candidates"]
    return result


def advance(client: TestClient, check: dict, run: dict) -> dict:
    response = client.post(
        check["base"] + "/advance",
        json={
            "run_id": run["id"],
            "revision": run["processing"]["revision"],
            "chunk_size": 2,
        },
    )
    assert response.status_code == 200, response.json()
    return response.json()


def choose(
    client: TestClient,
    check: dict,
    index: int | None = 0,
    revision: int = 0,
    generation: int = 1,
) -> dict:
    candidate = check["candidates"][index]["id"] if index is not None else None
    response = client.post(
        check["base"] + f"/records/{check['record']}/choice",
        json=body(
            candidate,
            revision=revision,
            generation=generation,
            key=f"result_choice_{check['process_id']}_{revision}",
            reason="Bukti diperiksa" if revision else "",
        ),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def test_partial_choice_appears_in_results_history_and_csv_without_changing_source(
    client: TestClient, db_session: Session, partial: dict
) -> None:
    source_before = dict(db_session.get(SourceRecord, partial["record"]).data)
    selected = choose(client, partial)
    result = client.get(partial["base"] + "/results")
    assert result.status_code == 200, result.json()
    value = result.json()
    assert value["total"] == 1
    summary = value["summary"]
    assert summary["total_targets"] == 5
    assert summary["saved_rows"] == 2
    assert summary["not_processed"] == 3
    assert summary["chosen_count"] == 1
    assert summary["not_selected"] == 4
    assert summary["partial"] is True
    assert value["items"][0]["choice"] == selected["current"]
    assert value["items"][0]["choice"]["candidate"]["fields"]["idpel"] == "002"
    assert client.get(partial["base"]).json()["current_generation"] == 0
    legacy_summary = client.get(f"/process/{partial['process_id']}/summary").json()
    assert legacy_summary["chosen_count"] == legacy_summary["valid_count"] == 1
    history = next(
        item
        for item in client.get("/history/processes").json()
        if item["id"] == partial["process_id"]
    )
    assert history["saved_rows"] == 2 and history["total_targets"] == 5
    assert history["chosen_count"] == 1
    events = client.get(partial["base"] + "/results/history").json()
    assert events["total"] == 1
    assert events["items"][0]["revision"] == 1
    assert events["items"][0]["row_number"] == 2
    for url in [
        partial["base"] + "/results/export",
        f"/process/{partial['process_id']}/export",
    ]:
        response = client.get(url)
        assert response.status_code == 200, response.text
        exported = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
        assert len(exported) == 1
        assert exported[0]["IDPEL_DIPILIH"] == "002"
        assert exported[0]["PETUGAS"] == "Petugas Uji"
        assert exported[0]["LAT_SEBELUM"] == "-6.2"
        assert '"filename"' in exported[0]["BUKTI_SUMBER_JSON"]
    assert db_session.get(SourceRecord, partial["record"]).data == source_before
    wrong = (
        "idpel_kosong" if partial["kind"] != "idpel_kosong" else "idpel_tidak_ketemu"
    )
    assert (
        client.get(
            partial["base"].replace(partial["kind"], wrong) + "/results"
        ).status_code
        == 404
    )


def test_replacement_cancellation_filters_and_history_are_not_counted_as_extra_choices(
    client: TestClient, partial: dict
) -> None:
    choose(client, partial)
    choose(client, partial, index=1, revision=1)
    result = client.get(partial["base"] + "/results").json()
    assert result["total"] == result["summary"]["chosen_count"] == 1
    assert result["summary"]["decision_events"] == 2
    assert result["items"][0]["choice"]["candidate"]["fields"]["idpel"] == "003"
    assert (
        client.get(partial["base"] + "/results", params={"q": "Second"}).json()["total"]
        == 1
    )
    assert (
        client.get(partial["base"] + "/results", params={"q": "No match"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        client.get(
            partial["base"] + "/results", params={"status": "not_processed"}
        ).json()["total"]
        == 3
    )
    choose(client, partial, index=None, revision=2)
    result = client.get(partial["base"] + "/results").json()
    assert result["total"] == result["summary"]["chosen_count"] == 0
    assert result["summary"]["cancelled_count"] == 1
    assert result["summary"]["decision_events"] == 3
    assert (
        client.get(partial["base"] + "/results", params={"status": "cancelled"}).json()[
            "total"
        ]
        == 1
    )
    assert (
        client.get(
            partial["base"] + "/results",
            params={"status": "all", "skip": 4, "limit": 1},
        ).json()["items"][0]["row_number"]
        == 6
    )
    events = client.get(partial["base"] + "/results/history").json()
    assert [item["revision"] for item in events["items"]] == [3, 2, 1]
    assert events["items"][0]["candidate_id"] is None
    assert len(client.get(partial["base"] + "/results/export").text.splitlines()) == 1


def test_resume_and_new_search_preserve_choices_and_allow_historical_result_export(
    client: TestClient, partial: dict
) -> None:
    selected = choose(client, partial)
    run = partial["latest_run"]
    for _ in range(12):
        if run["status"] == "completed":
            break
        run = advance(client, partial, run)
    assert run["status"] == "completed"
    before = client.get(partial["base"] + "/results").json()
    assert before["summary"]["partial"] is False
    assert before["summary"]["saved_rows"] == 5
    assert before["items"][0]["choice"] == selected["current"]
    retried = client.post(
        partial["base"] + "/retry",
        json={
            "latest_run_id": run["id"],
            "radius_meters": 100,
            "actor": "Petugas",
            "request_key": "result_retry_1",
            "incremental": True,
        },
    )
    assert retried.status_code == 200, retried.json()
    run = retried.json()["latest_run"]
    preparing = client.get(partial["base"] + "/results").json()
    assert preparing["summary"]["generation"] == 2
    assert preparing["summary"]["saved_rows"] == 0
    assert preparing["items"][0]["choice"] == selected["current"]
    for _ in range(2):
        run = advance(client, partial, run)
    partial["candidates"] = client.get(
        f"/corrections/{partial['kind']}/records/{partial['record']}",
        params={"process_id": partial["process_id"]},
    ).json()["candidates"]
    choose(client, partial, index=1, revision=1, generation=2)
    current = client.get(partial["base"] + "/results").json()
    historical = client.get(
        partial["base"] + "/results", params={"generation": 1}
    ).json()
    assert current["items"][0]["choice"]["candidate"]["fields"]["idpel"] == "003"
    assert historical["items"][0]["choice"]["candidate"]["fields"]["idpel"] == "002"
    export = client.get(partial["base"] + "/results/export", params={"generation": 1})
    assert (
        next(csv.DictReader(io.StringIO(export.text.lstrip("\ufeff"))))["IDPEL_DIPILIH"]
        == "002"
    )
    assert (
        client.get(partial["base"] + "/results", params={"generation": 99}).status_code
        == 404
    )


def test_latest_choice_is_scoped_to_its_process_even_for_the_same_source_row(
    client: TestClient, partial: dict
) -> None:
    choose(client, partial)
    checked = client.post(
        f"/corrections/{partial['kind']}/checks",
        json={
            "batch_id": partial["batch_id"],
            "pdpj_review_id": partial["pdpj_review_id"],
            "radius_meters": 10,
            "actor": "Petugas",
            "request_key": "second_result_scope",
            "incremental": True,
        },
    ).json()
    other = {
        **checked,
        "base": f"/corrections/{partial['kind']}/checks/{checked['process_id']}",
        "record": partial["record"],
    }
    run = checked["latest_run"]
    for _ in range(2):
        run = advance(client, other, run)
    other["candidates"] = client.get(
        f"/corrections/{partial['kind']}/records/{partial['record']}",
        params={"process_id": checked["process_id"]},
    ).json()["candidates"]
    choose(client, other, index=1)
    first = client.get(partial["base"] + "/results").json()
    second = client.get(other["base"] + "/results").json()
    assert first["items"][0]["choice"]["candidate"]["fields"]["idpel"] == "002"
    assert second["items"][0]["choice"]["candidate"]["fields"]["idpel"] == "003"
    assert first["summary"]["chosen_count"] == second["summary"]["chosen_count"] == 1


def test_csv_escapes_spreadsheet_formulas_without_changing_saved_decision(
    client: TestClient, partial: dict
) -> None:
    request = body(partial["candidates"][0]["id"], key="csv_formula_actor")
    request["actor"] = "=SUM(1,1)"
    url = partial["base"] + f"/records/{partial['record']}/choice"
    assert client.post(url, json=request).status_code == 200
    response = client.get(partial["base"] + "/results/export")
    row = next(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert row["PETUGAS"] == "'=SUM(1,1)"
    assert row["IDPEL_DIPILIH"] == "002"
    assert client.get(url).json()["current"]["actor"] == "=SUM(1,1)"
