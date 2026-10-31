"""Activity survives page reloads, rejects duplicate work, and releases on failure."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import processing_activity
from app.database import Base, get_db
from app.modules.corrections.router import router as correction_router
from app.modules.corrections.writer import SearchWriter
from app.modules.pdpj import service as pdpj_service
from app.modules.pdpj.router import router as pdpj_router
from app.modules.upload.router import router as upload_router
from app.processing_activity import activity_lock, request_activity
from app.sqlite_runtime import configure_sqlite_engine
from tests.test_corrections import upload


@pytest.fixture
def concurrent_client(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'activity.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    configure_sqlite_engine(engine)
    Base.metadata.create_all(engine)
    app = FastAPI()
    for router in (upload_router, pdpj_router, correction_router):
        app.include_router(router)

    def independent_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = independent_session
    with TestClient(app) as client:
        yield client
    engine.dispose()


@pytest.mark.parametrize("family", ["pdpj", "correction"])
def test_inflight_status_is_readable_and_pause_prevents_duplicate_work(
    concurrent_client: TestClient, monkeypatch: pytest.MonkeyPatch, family: str
) -> None:
    client = concurrent_client
    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n")
    batch = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n" * 1)
    if family == "pdpj":
        batch = upload(client, "pdpj", "IDPEL,LAT,LON\n" + "002,-6.2,106.8\n" * 3)
        review = client.post(
            "/pdpj/reviews", json={"batch_id": batch, "incremental": True}
        ).json()
        base = f"/pdpj/reviews/{review['id']}"
        revision = review["revision"]
        identity = {}
    else:
        review = client.post("/pdpj/reviews", json={"batch_id": batch}).json()
        assert (
            client.post(
                f"/pdpj/reviews/{review['id']}/complete",
                json={"revision": review["revision"], "actor": "Petugas"},
            ).status_code
            == 200
        )
        target = upload(
            client, "idpel_kosong", "NAMA,LAT,LON\n" + "Target,-6.2,106.8\n" * 3
        )
        check = client.post(
            "/corrections/idpel_kosong/checks",
            json={
                "batch_id": target,
                "pdpj_review_id": review["id"],
                "radius_meters": 10,
                "actor": "Petugas",
                "request_key": "activity_check_1",
                "incremental": True,
            },
        ).json()
        base = f"/corrections/idpel_kosong/checks/{check['process_id']}"
        run = check["latest_run"]
        prepared = client.post(
            base + "/advance",
            json={"run_id": run["id"], "revision": run["processing"]["revision"]},
        ).json()
        revision = prepared["processing"]["revision"]
        identity = {"run_id": run["id"]}
    entered, release = Event(), Event()
    original = (
        pdpj_service.match_processing_chunk if family == "pdpj" else SearchWriter.flush
    )

    def blocked(*args, **kwargs):
        result = original(*args, **kwargs)
        entered.set()
        assert release.wait(15), "Test did not release the active transaction"
        return result

    if family == "pdpj":
        monkeypatch.setattr(pdpj_service, "match_processing_chunk", blocked)
    else:
        monkeypatch.setattr(SearchWriter, "flush", blocked)
    with ThreadPoolExecutor(max_workers=2) as executor:
        active = executor.submit(
            client.post,
            base + "/advance",
            json={**identity, "revision": revision, "chunk_size": 1},
        )
        try:
            assert entered.wait(10)
            status = client.get(base + "/progress")
            assert status.status_code == 200, status.json()
            assert status.json()["activity"]["active"] is True
            assert status.json()["processing"]["processed_rows"] == 0
            duplicate = client.post(
                base + "/advance",
                json={**identity, "revision": revision, "chunk_size": 1},
            )
            assert duplicate.status_code == 409
            pause = executor.submit(client.post, base + "/pause", json=identity)
            deadline = monotonic() + 3
            while monotonic() < deadline:
                if (
                    client.get(base + "/progress").json()["activity"]["operation"]
                    == "pausing"
                ):
                    break
                sleep(0.02)
            else:
                pytest.fail(
                    f"Pause intent was not visible: {pause.result().status_code if pause.done() else 'pending'}; {client.get(base + '/progress').json()['activity']}"
                )
            assert client.post(base + "/resume", json=identity).status_code == 409
        finally:
            release.set()
        assert active.result(timeout=5).status_code == 200
        assert pause.result(timeout=5).status_code == 200
    saved = client.get(base + "/progress").json()
    assert saved["activity"]["active"] is False
    assert saved["processing"]["state"] == "paused"
    assert saved["processing"]["processed_rows"] == 1
    assert saved["processing"]["last_row_number"] == 2


def test_activity_is_not_inferred_from_saved_state_and_releases_after_exception(
    db_session: Session,
) -> None:
    assert not request_activity(db_session, "pdpj", 42)["active"]
    with pytest.raises(RuntimeError), activity_lock(db_session, "pdpj", 42, "matching"):
        assert request_activity(db_session, "pdpj", 42)["active"]
        raise RuntimeError("Worker failed")
    assert not request_activity(db_session, "pdpj", 42)["active"]


def test_process_exit_cannot_leave_a_stale_active_lock(tmp_path: Path) -> None:
    database = tmp_path / "shared.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    code = "from sqlalchemy import create_engine; from sqlalchemy.orm import Session; from app.processing_activity import activity_lock; import sys,os\nwith Session(create_engine(sys.argv[1])) as db, activity_lock(db, 'pdpj', 9, 'matching'):\n print('locked', flush=True)\n sys.stdin.readline()\n os._exit(7)\n"
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(engine.url)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        **(
            {"creationflags": subprocess.CREATE_NO_WINDOW}
            if sys.platform == "win32"
            else {}
        ),
    )
    try:
        assert child.stdout.readline().strip() == "locked"
        with Session(engine) as db:
            assert request_activity(db, "pdpj", 9)["active"]
            child.stdin.write("exit\n")
            child.stdin.flush()
            child.wait(timeout=5)
            assert not request_activity(db, "pdpj", 9)["active"]
    finally:
        if child.poll() is None:
            child.stdin.write("exit\n")
            child.stdin.flush()
            child.wait(timeout=5)
        engine.dispose()


def test_postgres_activity_uses_shared_advisory_locks_and_releases_them(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    held: set[int] = set()

    class Connection:
        def execute(self, statement, parameters):
            key = parameters["key"]
            if "pg_try_advisory_lock" in str(statement):
                acquired = key not in held
                if acquired:
                    held.add(key)
                return SimpleNamespace(scalar=lambda: acquired)
            held.remove(key)
            return SimpleNamespace(scalar=lambda: True)

    @contextmanager
    def connect():
        yield Connection()

    engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"), connect=connect
    )
    monkeypatch.setattr(processing_activity, "database_engine", lambda _db: engine)
    with activity_lock(db_session, "pdpj", 7, "matching"):
        assert request_activity(db_session, "pdpj", 7)["active"]
        assert not request_activity(db_session, "pdpj", 8)["active"]
    assert not held
    assert not request_activity(db_session, "pdpj", 7)["active"]
