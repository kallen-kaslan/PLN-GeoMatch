"""Two-step not-found analysis and candidate search use one prepared snapshot."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.correction import CorrectionCheck
from app.models.matching import ReconciliationProcess
from tests.test_corrections import reference, upload


def test_not_found_analysis_exclusions_snapshot_reuse_and_category_scope(client: TestClient, reference: int, db_session: Session) -> None:
    batch = upload(client, "idpel_tidak_ketemu", "IDPEL,NAMA,LAT,LON,NOMOR_METER,ID_TITIK,DAYA\n001,Already PDPJ,-9,110,,,\n222,Search,-6.2,106.8,M001,S001,bad\n333,Bad coordinates,95,106.8,,,\n")
    base = "/corrections/idpel_tidak_ketemu/radius-analyses"
    body = {"batch_id": batch, "actor": "Tester", "request_key": "notfound-analysis-key"}
    created = client.post(base, json=body)
    assert created.status_code == 200, created.text
    item = created.json()
    identity = item["id"]
    assert client.post(base, json=body).json()["id"] == identity
    wrong = "/corrections/idpel_kosong/radius-analyses"
    assert client.post(wrong, json={**body, "request_key": "wrong-category-key"}).status_code == 404
    assert client.get(f"{wrong}/{identity}").status_code == 404
    assert client.get(wrong + "/workflow", params={"batch_id": batch}).status_code == 404
    assert client.post(f"{wrong}/{identity}/analysis-job", json={"state": "running"}).status_code == 404
    assert client.post(f"{wrong}/{identity}/search-job", json={"state": "running", "radius_meters": 5, "request_key": "wrong-search-key"}).status_code == 404
    # Restore and coverage reads never advance or create a search.
    before = client.get(base + "/workflow", params={"batch_id": batch, "analysis_id": identity}).json()
    assert before["search"] is None and before["analysis"]["processed_rows"] == 0
    for _ in range(80):
        if item["state"] == "ready":
            break
        response = client.post(f"{base}/{identity}/advance", json={"revision": item["revision"]})
        assert response.status_code == 200, response.text
        item = response.json()
    assert item["state"] == "ready"
    assert item["recommended_radius_meters"] == 5
    assert item["idpel_in_pdpj_rows"] == 1 and item["coordinate_rows"] == 1
    assert item["eligible_rows"] == item["covered_rows"] == 1
    coverage = client.get(f"{base}/{identity}", params={"radius_meters": 5}).json()
    assert coverage["coverage_rows"] == 1
    assert client.get(base + "/workflow", params={"batch_id": batch}).json()["search"] is None
    # Identity exclusion is already visible before creating candidate search.
    overview = client.get("/corrections/idpel_tidak_ketemu/overview/records", params={"status": "idpel_in_pdpj"}).json()
    assert overview["total"] == 1
    blocked_row = overview["items"][0]
    assert blocked_row["process_id"] is None and blocked_row["analysis_id"] == identity
    evidence = client.get(f"/corrections/idpel_tidak_ketemu/records/{blocked_row['id']}", params={"analysis_id": identity}).json()
    assert evidence["conflicts"][0]["code"] == "idpel_sama_pdpj"
    assert evidence["conflicts"][0]["fields"]["idpel"] == "001"
    assert client.get("/corrections/idpel_tidak_ketemu/overview/summary").json()["counts"]["idpel_in_pdpj"] == 1
    saved = client.put(f"{base}/{identity}/radius", json={"revision": item["revision"], "radius_meters": 5}).json()
    search = client.post(f"{base}/{identity}/search", json={"revision": saved["revision"], "request_key": "notfound-search-key"})
    assert search.status_code == 200, search.text
    process_id = search.json()["process_id"]
    check = db_session.query(CorrectionCheck).filter_by(process_id=process_id).one()
    assert check.category == "idpel_tidak_ketemu"
    analysis_process = db_session.query(ReconciliationProcess).filter_by(target_batch_id=batch, process_name="Analisis radius idpel tidak ketemu").one()
    process = db_session.get(ReconciliationProcess, process_id)
    assert process.master_snapshot_id == analysis_process.master_snapshot_id
    assert process.source_batches == analysis_process.source_batches
    path = f"/corrections/idpel_tidak_ketemu/checks/{process_id}"
    progress = client.get(path + "/progress").json()
    assert progress["processing"]["stage"] == "matching"
    for _ in range(30):
        if progress["status"] == "completed":
            break
        response = client.post(path + "/advance", json={"run_id": progress["id"], "revision": progress["processing"]["revision"], "chunk_size": 1})
        assert response.status_code == 200, response.text
        progress = response.json()
    assert progress["status"] == "completed"
    workflow = client.get(base + "/workflow", params={"batch_id": batch}).json()
    assert workflow["search"]["matched_rows"] == workflow["search"]["idpel_in_pdpj_rows"] == workflow["search"]["coordinate_rows"] == 1
    assert workflow["search"]["processed_rows"] == 3
    rows = client.get("/corrections/idpel_tidak_ketemu/overview/records").json()["items"]
    assert {row["fields"]["idpel"]: row["status"] for row in rows} == {"001": "idpel_in_pdpj", "222": "candidates_found", "333": "coordinate_issues"}


def finish_analysis(client, base, item):
    for _ in range(80):
        if item["state"] == "ready":
            return item
        response = client.post(f"{base}/{item['id']}/advance", json={"revision": item["revision"]})
        assert response.status_code == 200, response.text
        item = response.json()
    raise AssertionError("Analysis did not finish")


def finish_search(client, base, item, radius=5):
    saved = client.put(f"{base}/{item['id']}/radius", json={"revision": item["revision"], "radius_meters": radius}).json()
    response = client.post(f"{base}/{item['id']}/search", json={"revision": saved["revision"], "request_key": f"search-analysis-{item['id']}"})
    assert response.status_code == 200, response.text
    process_id = response.json()["process_id"]
    path = f"/corrections/idpel_tidak_ketemu/checks/{process_id}"
    run = client.get(path + "/progress").json()
    for _ in range(80):
        if run["status"] == "completed":
            return process_id
        response = client.post(path + "/advance", json={"run_id": run["id"], "revision": run["processing"]["revision"], "chunk_size": 1})
        assert response.status_code == 200, response.text
        run = response.json()
    raise AssertionError("Search did not finish")


def test_new_coordinate_policy_does_not_reinterpret_legacy_analysis(client: TestClient, reference: int, db_session: Session) -> None:
    from app.models.radius_analysis import RadiusAnalysis
    from app.modules.corrections.empty_rules import TARGET_POLICY_KEY, COORDINATE_IDPEL_POLICY
    batch = upload(client, "idpel_tidak_ketemu", "IDPEL,NOMOR_METER,ID_TITIK,LAT,LON\n000777,M001,S001,-6.2,106.8\n")
    base = "/corrections/idpel_tidak_ketemu/radius-analyses"
    legacy = client.post(base, json={"batch_id": batch, "actor": "Tester", "request_key": "legacy-policy-analysis"}).json()
    stored = db_session.get(RadiusAnalysis, legacy["id"])
    stored.progress = {}  # Simulate a checkpoint created before policy versioning.
    db_session.commit()
    legacy = finish_analysis(client, base, client.get(f"{base}/{legacy['id']}").json())
    assert legacy["reference_conflict_rows"] == 1 and legacy["eligible_rows"] == 0
    legacy_process = finish_search(client, base, legacy)
    before = client.get("/corrections/idpel_tidak_ketemu/records", params={"process_id": legacy_process}).json()["items"]
    assert before[0]["search_status"] == "pdpj_conflict"
    current = client.post(base, json={"batch_id": batch, "actor": "Tester", "request_key": "coordinate-policy-analysis"}).json()
    assert current["id"] != legacy["id"] and current["progress"][TARGET_POLICY_KEY] == COORDINATE_IDPEL_POLICY
    current = finish_analysis(client, base, current)
    assert current["eligible_rows"] == 1 and current["reference_conflict_rows"] == 0
    current_process = finish_search(client, base, current)
    after = client.get("/corrections/idpel_tidak_ketemu/records", params={"process_id": current_process}).json()["items"]
    assert after[0]["search_status"] == "matched" and after[0]["conflicts"] == []
    historical = client.get("/corrections/idpel_tidak_ketemu/records", params={"process_id": legacy_process}).json()["items"]
    assert historical == before


def test_missing_idpel_coordinate_issues_and_outside_limit_are_disjoint(client: TestClient, reference: int) -> None:
    batch = upload(client, "idpel_tidak_ketemu", "IDPEL,LAT,LON\n001,,\n,-6.2,106.8\ninvalid,-6.2,106.8\n000777,-6.2,106.8\n888,95,106.8\n999,-9,110\n")
    base = "/corrections/idpel_tidak_ketemu/radius-analyses"
    item = client.post(base, json={"batch_id": batch, "actor": "Tester", "request_key": "notfound-disjoint-analysis"}).json()
    item = finish_analysis(client, base, item)
    assert item["idpel_in_pdpj_rows"] == 1 and item["coordinate_rows"] == 1 and item["category_rows"] == 2
    assert item["covered_rows"] == item["outside_limit_rows"] == 1
    assert item["recommended_radius_meters"] is None and item["partial_radius_meters"] == 5
    assert item["eligible_rows"] + item["invalid_rows"] == item["total_rows"] == 6
    finish_search(client, base, item)
    job = client.get(base + "/workflow", params={"batch_id": batch}).json()["search"]
    assert job["processed_rows"] == 6
    assert job["matched_rows"] == job["no_candidate_rows"] == job["coordinate_rows"] == job["idpel_in_pdpj_rows"] == 1
    assert job["other_issue_rows"] - job["idpel_in_pdpj_rows"] == 2
    assert job["matched_rows"] + job["no_candidate_rows"] + job["coordinate_rows"] + job["other_issue_rows"] == 6
