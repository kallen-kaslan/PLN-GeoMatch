"""Progress reflects real work without exposing uncommitted imports as ready data."""

from typing import Any

from app.models.upload import SourceRecord, UploadBatch
from app.modules.upload.progress import UploadProgress, read_progress
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_progress_reports_bytes_and_chunk_counts_through_confirmation(
    client: TestClient, db_session: Session, monkeypatch: Any
) -> None:
    from app.modules.upload import ingestion, router

    monkeypatch.setattr(ingestion, "IMPORT_CHUNK_ROWS", 2)
    monkeypatch.setattr(router, "IMPORT_CHUNK_ROWS", 2)
    snapshots = []
    original = UploadProgress.update

    def observe(self: UploadProgress, processed: int, total: int | None = None) -> None:
        original(self, processed, total)
        snapshots.append(dict(self.snapshot))

    monkeypatch.setattr(UploadProgress, "update", observe)
    token = client.post("/upload/progress").json()["id"]
    headers = {"X-Upload-Progress": token}
    content = b"IDPEL,NAMA,LAT,LON\n" + b"001,Pelanggan,-6.2,106.8\n" * 5
    stored = client.post(
        "/upload/files", headers=headers, files={"file": ("dil.csv", content)}
    )
    assert stored.status_code == 200, stored.text
    assert any(
        item["phase"] == "archiving" and item["processed"] == len(content)
        for item in snapshots
    )
    response = client.post(
        f"/upload/files/{stored.json()['id']}/import-sheet",
        headers=headers,
        json={"dataset_type": "dil"},
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["id"]
    assert [item["processed"] for item in snapshots if item["phase"] == "reading"] == [
        2,
        4,
        5,
    ]
    assert client.get("/master/dil/summary").json()["total_rows"] == 0
    snapshots.clear()
    response = client.post(
        "/upload/confirm-mapping",
        headers=headers,
        json={"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
    )
    assert response.status_code == 200, response.text
    assert [
        item["processed"] for item in snapshots if item["phase"] == "validating"
    ] == [2, 4, 5]
    assert all(
        item["total"] == 5 for item in snapshots if item["phase"] == "validating"
    )
    snapshot = client.get(f"/upload/progress/{token}").json()
    assert snapshot["status"] == "completed"
    assert snapshot["phase"] == "finalizing"
    assert snapshot["total"] == snapshot["processed"] == 5
    # A fresh tracker, as used by a different web worker, reads the same state.
    assert UploadProgress(token).snapshot == {
        key: value for key, value in snapshot.items() if key != "pause_requested"
    }
    assert db_session.get(UploadBatch, batch_id).status.value == "completed"


def test_failed_mapping_retains_pending_batch_and_reports_failure(
    client: TestClient, db_session: Session
) -> None:
    stored = client.post(
        "/upload/files", files={"file": ("dil.csv", b"IDPEL\n001\n")}
    ).json()
    batch = client.post(
        f"/upload/files/{stored['id']}/import-sheet", json={"dataset_type": "dil"}
    ).json()
    token = client.post("/upload/progress").json()["id"]
    response = client.post(
        "/upload/confirm-mapping",
        headers={"X-Upload-Progress": token},
        json={"batch_id": batch["id"], "column_mapping": {"idpel": "MISSING"}},
    )
    assert response.status_code == 422
    assert read_progress(token)["status"] == "failed"
    assert db_session.get(UploadBatch, batch["id"]).status.value == "needs_mapping"
    assert (
        db_session.query(SourceRecord)
        .filter_by(batch_id=batch["id"])
        .first()
        .normalized_data
        is None
    )
    assert client.get("/master/dil/summary").json()["total_rows"] == 0


def test_progress_token_is_validated_and_unknown_ids_do_not_start_imports(
    client: TestClient,
) -> None:
    assert client.get("/upload/progress/not-a-token").status_code == 422
    assert client.get(f"/upload/progress/{'a' * 32}").status_code == 404
    response = client.post(
        "/upload/files",
        headers={"X-Upload-Progress": "a" * 32},
        files={"file": ("dil.csv", b"IDPEL\n001\n")},
    )
    assert response.status_code == 404
    assert client.get("/upload/files").json() == []


def test_status_file_contention_does_not_fail_a_successful_import(
    client: TestClient, monkeypatch: Any
) -> None:
    from app.modules.upload import progress

    stored = client.post(
        "/upload/files", files={"file": ("dil.csv", b"IDPEL\n001\n")}
    ).json()
    batch = client.post(
        f"/upload/files/{stored['id']}/import-sheet", json={"dataset_type": "dil"}
    ).json()
    token = client.post("/upload/progress").json()["id"]

    def locked_status(*args: Any) -> None:
        raise PermissionError("Snapshot is being read")

    monkeypatch.setattr(progress.os, "replace", locked_status)
    response = client.post(
        "/upload/confirm-mapping",
        headers={"X-Upload-Progress": token},
        json={"batch_id": batch["id"], "column_mapping": {"idpel": "IDPEL"}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["rows"] == 1
    assert client.get("/master/dil/summary").json()["total_rows"] == 1
