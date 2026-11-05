"""Phase-one overview uses saved outcomes; no live database or search changes."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.correction import CorrectionTarget
from app.models.matching import ReconciliationProcess
from tests.test_corrections import check, reference, upload


def test_not_found_summary_filter_identity_evidence_and_category_isolation(client: TestClient, reference: int, db_session: Session) -> None:
    batch = upload(client, "idpel_tidak_ketemu", "objectid,IDPEL,NAMA,LAT,LON,NOAGENDA,NOMOR_METER,ID_TITIK\n701,001,IDPEL PDPJ,,,A1,,S1\n702,222,Kandidat,-6.2,106.8,A2,,S2\n703,333,Jauh,-9,110,A3,,S3\n704,444,Tanpa koordinat,,,A4,,S4\n705,555,Meter sama,-6.2,106.8,A5,M001,S5\n")
    result = check(client, "idpel_tidak_ketemu", batch, reference)
    upload(client, "idpel_tidak_ketemu", "IDPEL,NAMA,LAT,LON\n000666,Belum diperiksa,-6.2,106.8\n")
    upload(client, "idpel_kosong", "NAMA,LAT,LON\nKategori lain,-6.2,106.8\n")
    before = (db_session.query(ReconciliationProcess).count(), db_session.query(CorrectionTarget).count())
    base = "/corrections/idpel_tidak_ketemu/overview"
    summary = client.get(base + "/summary")
    assert summary.status_code == 200
    assert summary.json() == {"total_rows": 6, "counts": {"idpel_in_pdpj": 1, "candidates_found": 1, "no_candidates": 1, "coordinate_issues": 1, "not_processed": 2}}
    all_rows = client.get(base + "/records").json()
    assert len(all_rows["items"]) == all_rows["total"] == 6
    blocked = client.get(base + "/records", params={"status": "idpel_in_pdpj"}).json()
    assert blocked["total"] == 1
    row = blocked["items"][0]
    assert row["object_id"] == "701" and row["fields"]["idpel"] == "001"
    assert row["process_id"] == result["process_id"] and row["candidate_count"] == 0
    detail = client.get(f"/corrections/idpel_tidak_ketemu/records/{row['id']}", params={"process_id": row["process_id"], "generation": row["generation"]}).json()
    assert detail["conflicts"][0]["code"] == "idpel_sama_pdpj"
    assert detail["conflicts"][0]["fields"]["idpel"] == "001"
    assert detail["candidates_total"] == 0
    assert client.get(base + "/records", params={"q": "000666"}).json()["total"] == 1
    assert client.get(base + "/records", params={"q": "555", "status": "not_processed"}).json()["total"] == 1
    assert client.get(base + "/records", params={"status": "bad"}).status_code == 422
    assert client.get(base + "/records", params={"limit": 101}).status_code == 422
    assert client.get(base + "/records", params={"skip": 5, "limit": 1}).json()["items"] == all_rows["items"][5:6]
    assert client.get("/corrections/idpel_kosong/overview/summary").json()["total_rows"] == 1
    assert before == (db_session.query(ReconciliationProcess).count(), db_session.query(CorrectionTarget).count())
    pending = client.get("/corrections/idpel_tidak_ketemu/workflow/pending").json()
    assert len(pending) == 1 and pending[0]["filename"] == "idpel_tidak_ketemu.csv"
    assert pending[0]["stage"] == "analysis" and pending[0]["process_id"] is None


def test_not_found_overview_retains_saved_results_during_new_run(client: TestClient, reference: int) -> None:
    batch = upload(client, "idpel_tidak_ketemu", "IDPEL,LAT,LON\n001,-6.2,106.8\n222,-6.2,106.8\n")
    result = check(client, "idpel_tidak_ketemu", batch, reference)
    base = "/corrections/idpel_tidak_ketemu/overview"
    before = client.get(base + "/records").json()
    retry = client.post(f"/corrections/idpel_tidak_ketemu/checks/{result['process_id']}/retry", json={"latest_run_id": result["latest_run"]["id"], "radius_meters": 20, "actor": "Petugas Uji", "request_key": "not_found_pending_retry", "incremental": True})
    assert retry.status_code == 200
    after = client.get(base + "/records").json()
    assert [(row["id"], row["status"], row["generation"]) for row in after["items"]] == [(row["id"], row["status"], row["generation"]) for row in before["items"]]
    assert client.get(base + "/summary").json()["counts"] == {"idpel_in_pdpj": 1, "candidates_found": 1}
