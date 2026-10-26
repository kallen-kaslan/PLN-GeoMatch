"""Worker redelivery and failure behavior on isolated, process-bound datasets."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest
from celery.exceptions import Retry
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.matching import (
    MatchCandidate,
    MatchingRun,
    ProcessStatus,
    ReconciliationProcess,
)
from app.models.upload import DatasetType
from app.modules.spatial.engine import create_matching_run, run_spatial_matching_job
from app.modules.spatial.pipeline import pin_pipeline_sources
from app.tasks import spatial_tasks
from tests.test_foundations import batch, setup_matching


def test_worker_redelivery_keeps_candidates_and_decisions(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_id, target_id = setup_matching(db_session)
    process = ReconciliationProcess(
        process_name="worker", master_snapshot_id=snapshot_id, target_batch_id=target_id
    )
    db_session.add(process)
    db_session.flush()
    run = create_matching_run(db_session, process, 100, 5)
    db_session.commit()
    process_id, run_id = process.id, run.id
    monkeypatch.setattr(spatial_tasks, "SessionLocal", lambda: db_session)
    arguments = {
        "process_id": process_id,
        "process_name": "worker",
        "target_batch_id": target_id,
        "run_id": run_id,
    }
    first = spatial_tasks.execute_matching_task.run(**arguments)
    candidate = db_session.query(MatchCandidate).order_by(MatchCandidate.id).first()
    candidate.is_accepted = 1
    candidate_id = candidate.id
    db_session.commit()
    assert spatial_tasks.execute_matching_task.run(**arguments) == first
    assert db_session.query(MatchCandidate).count() == 2
    assert db_session.get(MatchCandidate, candidate_id).is_accepted == 1


@pytest.mark.parametrize("retries", [0, 2])
def test_failed_worker_attempt_keeps_active_history(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, retries: int
) -> None:
    _, target_id = setup_matching(db_session)
    original = run_spatial_matching_job(db_session, "failure", target_id)
    process = db_session.get(ReconciliationProcess, original["process_id"])
    run = create_matching_run(db_session, process, 10, 5)
    db_session.commit()
    process_id, run_id = process.id, run.id
    monkeypatch.setattr(spatial_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        spatial_tasks,
        "run_spatial_matching_job",
        Mock(side_effect=RuntimeError("failure")),
    )
    monkeypatch.setattr(
        spatial_tasks.execute_matching_task, "retry", Mock(side_effect=Retry("retry"))
    )
    task = spatial_tasks.execute_matching_task
    task.push_request(retries=retries)
    arguments = {
        "process_id": process_id,
        "process_name": "failure",
        "target_batch_id": target_id,
        "run_id": run_id,
    }
    try:
        if retries == 0:
            with pytest.raises(Retry):
                task.run(**arguments)
        else:
            assert task.run(**arguments)["status"] == "failed"
    finally:
        task.pop_request()
    assert db_session.get(MatchingRun, run_id).status == ProcessStatus.FAILED
    assert db_session.get(ReconciliationProcess, process_id).current_generation == 1
    assert db_session.query(MatchCandidate).count() == 2


def test_pipeline_worker_reuses_completed_attempt(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = batch(
        db_session,
        DatasetType.PASCABAYAR,
        [{"idpel": "0012", "lat": -6.2, "lon": 106.8}],
    )
    target = batch(db_session, DatasetType.TARGET, [{"lat": -6.2, "lon": 106.8}])
    process = ReconciliationProcess(
        process_name="pipeline worker",
        radius_meters=100,
        source_batches=pin_pipeline_sources(
            db_session, source.id, None, None, target.id
        ),
    )
    db_session.add(process)
    db_session.commit()
    process_id = process.id
    monkeypatch.setattr(spatial_tasks, "SessionLocal", lambda: db_session)
    first = spatial_tasks.execute_batch_reconciliation_pipeline.run(
        process_id=process_id
    )
    assert (
        spatial_tasks.execute_batch_reconciliation_pipeline.run(process_id=process_id)
        == first
    )
    assert db_session.query(MatchingRun).count() == 1


def test_pipeline_failure_records_status(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = ReconciliationProcess(
        process_name="bad pipeline", source_batches={"target": None}
    )
    db_session.add(process)
    db_session.commit()
    process_id = process.id
    monkeypatch.setattr(spatial_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        spatial_tasks, "execute_pipeline", Mock(side_effect=RuntimeError("failure"))
    )
    task = spatial_tasks.execute_batch_reconciliation_pipeline
    task.push_request(retries=1)
    try:
        assert task.run(process_id=process_id)["status"] == "failed"
    finally:
        task.pop_request()
    assert (
        db_session.get(ReconciliationProcess, process_id).matching_status
        == ProcessStatus.FAILED
    )


@pytest.mark.parametrize("task_kind", ["matching", "pipeline"])
def test_simultaneous_redelivery_publishes_one_candidate_set(
    tmp_path: Path, task_kind: str
) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'concurrent.db').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        snapshot_id, target_id = setup_matching(db)
        process = ReconciliationProcess(
            process_name="concurrent",
            master_snapshot_id=snapshot_id,
            target_batch_id=target_id,
        )
        if task_kind == "pipeline":
            from app.models.upload import UploadBatch

            source = (
                db.query(UploadBatch)
                .filter(UploadBatch.dataset_type == DatasetType.PASCABAYAR)
                .one()
            )
            process = ReconciliationProcess(
                process_name="concurrent pipeline",
                radius_meters=100,
                source_batches=pin_pipeline_sources(
                    db, source.id, None, None, target_id
                ),
            )
        db.add(process)
        db.flush()
        run = (
            create_matching_run(db, process, 100, 5)
            if task_kind == "matching"
            else None
        )
        db.commit()
        process_id, run_id = process.id, run.id if run else None

    def execute(_: int) -> dict:
        with sessions() as db:
            if task_kind == "pipeline":
                from app.modules.spatial.pipeline import execute_pipeline

                return execute_pipeline(db, process_id)
            return run_spatial_matching_job(
                db, "concurrent", target_id, process_id=process_id, run_id=run_id
            )

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(execute, [1, 2]))
    assert results[0] == results[1]
    with sessions() as db:
        assert db.query(MatchCandidate).count() == 2
        assert db.query(MatchingRun).count() == 1
    engine.dispose()
