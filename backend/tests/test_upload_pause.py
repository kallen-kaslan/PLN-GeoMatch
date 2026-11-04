"""Pause at real import chunks, release SQLite locks, and resume without duplicates."""

import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Semaphore
from typing import Any

import pytest
from app.database import Base, get_db
from app.models.upload import BatchStatus, SourceRecord, UploadBatch
from app.modules.upload.progress import UploadProgress
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def file_client(client: TestClient, tmp_path: Any):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'pause.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def session():
        with sessions() as db:
            yield db

    client.app.dependency_overrides[get_db] = session
    try:
        yield client, sessions
    finally:
        engine.dispose()


def wait_paused(client: TestClient, token: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = client.get(f"/upload/progress/{token}").json()
        if snapshot["status"] == "paused":
            return snapshot
        time.sleep(0.01)
    raise AssertionError("Server did not acknowledge the pause")


@pytest.mark.parametrize("phase", ["reading", "validating"])
def test_repeat_pause_resume_preserves_every_row_and_releases_database(
    file_client: Any, monkeypatch: Any, phase: str
) -> None:
    from app.modules.upload import ingestion, router

    client, sessions = file_client
    monkeypatch.setattr(ingestion, "IMPORT_CHUNK_ROWS", 2)
    monkeypatch.setattr(router, "IMPORT_CHUNK_ROWS", 2)
    content = b"IDPEL,NAMA,LAT,LON\n" + b"".join(
        f"{number:03},Pelanggan {number},-6.2,106.8\n".encode()
        for number in range(1, 6)
    )
    archive = client.post(
        "/upload/files", files={"file": ("pause.csv", content)}
    ).json()
    import_url = f"/upload/files/{archive['id']}/import-sheet"
    batch_id = None
    if phase == "validating":
        batch_id = client.post(import_url, json={"dataset_type": "dil"}).json()["id"]
    token = client.post("/upload/progress").json()["id"]
    headers = {"X-Upload-Progress": token}
    arrived: Queue[int] = Queue()
    permit = Semaphore(0)
    original_update = UploadProgress.update

    def measured(
        self: UploadProgress, processed: int, total: int | None = None
    ) -> None:
        original_update(self, processed, total)
        if (
            self.token == token
            and self.snapshot["phase"] == phase
            and processed in (2, 4)
        ):
            arrived.put(processed)
            assert permit.acquire(timeout=10)

    monkeypatch.setattr(UploadProgress, "update", measured)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.post,
            import_url if phase == "reading" else "/upload/confirm-mapping",
            headers=headers,
            json={"dataset_type": "dil"}
            if phase == "reading"
            else {"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
        )
        try:
            for expected in (2, 4):
                assert arrived.get(timeout=10) == expected
                assert client.post(f"/upload/progress/{token}/pause").status_code == 200
                permit.release()
                snapshot = wait_paused(client, token)
                assert snapshot["processed"] == expected
                assert snapshot["pause_requested"]
                assert not future.done()
                with sessions() as db:
                    batch = db.query(UploadBatch).filter_by(filename="pause.csv").one()
                    batch_id = batch.id
                    assert batch.status == BatchStatus.PROCESSING
                    assert db.query(SourceRecord).filter_by(
                        batch_id=batch_id
                    ).count() == (expected if phase == "reading" else 5)
                # A separate connection can write while the original request is paused.
                another = client.post(
                    "/upload/",
                    data={"dataset_type": "dil"},
                    files={"file": (f"other-{expected}.csv", b"IDPEL\n099\n")},
                )
                assert another.status_code == 200, another.text
                assert client.get("/master/dil/summary").json()["total_rows"] == 0
                duplicate = (
                    client.post(import_url, json={"dataset_type": "dil"})
                    if phase == "reading"
                    else client.post(
                        "/upload/confirm-mapping",
                        json={
                            "batch_id": batch_id,
                            "column_mapping": {"idpel": "IDPEL"},
                        },
                    )
                )
                assert duplicate.status_code == 409
                assert (
                    client.get(f"/upload/progress/{token}").json()["processed"]
                    == expected
                )
                # Repeating Resume does not start another worker or another import.
                for _ in range(2):
                    assert (
                        client.post(f"/upload/progress/{token}/resume").status_code
                        == 200
                    )
            result = future.result(timeout=10)
            assert result.status_code == 200, result.text
        finally:
            client.post(f"/upload/progress/{token}/resume")
            permit.release(3)
    if phase == "reading":
        result = client.post(
            "/upload/confirm-mapping",
            json={"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
        )
        assert result.status_code == 200, result.text
    with sessions() as db:
        batch = db.get(UploadBatch, batch_id)
        assert batch.status == BatchStatus.COMPLETED
        assert batch.total_rows == batch.valid_rows == 5
        records = (
            db.query(SourceRecord)
            .filter_by(batch_id=batch_id)
            .order_by(SourceRecord.row_number)
            .all()
        )
        assert [record.row_number for record in records] == [2, 3, 4, 5, 6]
        assert [record.normalized_data["idpel"] for record in records] == [
            "001",
            "002",
            "003",
            "004",
            "005",
        ]
    assert client.get("/master/dil/summary").json()["total_rows"] == 5


@pytest.mark.parametrize("phase", ["reading", "validating"])
def test_failure_after_resume_can_retry_without_missing_or_duplicate_rows(
    file_client: Any, monkeypatch: Any, phase: str
) -> None:
    from app.modules.upload import ingestion, router

    client, sessions = file_client
    monkeypatch.setattr(ingestion, "IMPORT_CHUNK_ROWS", 2)
    monkeypatch.setattr(router, "IMPORT_CHUNK_ROWS", 2)
    content = b"IDPEL\n001\n002\n003\n004\n005\n"
    archive = client.post(
        "/upload/files", files={"file": ("retry-pause.csv", content)}
    ).json()
    import_url = f"/upload/files/{archive['id']}/import-sheet"
    batch_id = None
    if phase == "validating":
        batch_id = client.post(import_url, json={"dataset_type": "dil"}).json()["id"]
    token = client.post("/upload/progress").json()["id"]
    arrived: Queue[int] = Queue()
    permit = Semaphore(0)
    original_update = UploadProgress.update

    def measured(
        self: UploadProgress, processed: int, total: int | None = None
    ) -> None:
        original_update(self, processed, total)
        if self.token == token and self.snapshot["phase"] == phase:
            if processed == 2:
                arrived.put(processed)
                assert permit.acquire(timeout=10)
            if processed == 4:
                if phase == "reading":
                    raise OSError("Simulated read failure after resuming")
                raise OperationalError(
                    "UPDATE", {}, Exception("Simulated write failure")
                )

    monkeypatch.setattr(UploadProgress, "update", measured)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.post,
            import_url if phase == "reading" else "/upload/confirm-mapping",
            headers={"X-Upload-Progress": token},
            json={"dataset_type": "dil"}
            if phase == "reading"
            else {"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
        )
        try:
            assert arrived.get(timeout=10) == 2
            client.post(f"/upload/progress/{token}/pause")
            permit.release()
            wait_paused(client, token)
            client.post(f"/upload/progress/{token}/resume")
            result = future.result(timeout=10)
            assert result.status_code == (400 if phase == "reading" else 500)
        finally:
            client.post(f"/upload/progress/{token}/resume")
            permit.release(2)
    with sessions() as db:
        batch = db.query(UploadBatch).filter_by(filename="retry-pause.csv").one()
        batch_id = batch.id
        assert batch.status == (
            BatchStatus.FAILED if phase == "reading" else BatchStatus.NEEDS_MAPPING
        )
        assert db.query(SourceRecord).filter_by(batch_id=batch_id).count() == (
            2 if phase == "reading" else 5
        )
    assert client.get("/master/dil/summary").json()["total_rows"] == 0
    if phase == "reading":
        assert (
            client.post(
                "/upload/confirm-mapping",
                json={"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
            ).status_code
            == 409
        )
        imported = client.post(import_url, json={"dataset_type": "dil"})
        assert imported.status_code == 200, imported.text
        assert imported.json()["id"] == batch_id
    result = client.post(
        "/upload/confirm-mapping",
        json={"batch_id": batch_id, "column_mapping": {"idpel": "IDPEL"}},
    )
    assert result.status_code == 200, result.text
    assert result.json()["rows"] == 5
    with sessions() as db:
        records = (
            db.query(SourceRecord)
            .filter_by(batch_id=batch_id)
            .order_by(SourceRecord.row_number)
            .all()
        )
        assert [record.normalized_data["idpel"] for record in records] == [
            "001",
            "002",
            "003",
            "004",
            "005",
        ]
