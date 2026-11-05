"""Not-found workers finish active rows before pause and resume durable checkpoints."""
from threading import Event, Thread
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session
from tests import test_empty_workflow as fixtures
from app.models.upload import DatasetType, SourceRecord, UploadBatch
from app.models.radius_analysis import RadiusAnalysis, RadiusAnalysisRow
from app.models.correction import CorrectionTarget, CorrectionCandidateEvidence
from app.modules.corrections.radius_router import start, StartAnalysis, analysis_job, search_job, JobRequest, SearchJobRequest
from app.modules.corrections.radius_analysis import nearest_eligible
from app.modules.corrections.engine import run_correction_matching


@pytest.fixture
def managed_not_found():
    helper = fixtures.EmptyWorkflowTests()
    helper.setUp()
    try:
        helper.db.get(UploadBatch, helper.batch_id).dataset_type = DatasetType.IDPEL_TIDAK_KETEMU
        helper.db.get(SourceRecord, helper.target_id).data = {"idpel": "777", "lat": -6.2, "lon": 106.8}
        helper.db.add(SourceRecord(batch_id=helper.batch_id, row_number=3, data={"idpel": "888", "lat": -6.2, "lon": 106.8}))
        helper.db.commit()
        helper.item_id = start(StartAnalysis(batch_id=helper.batch_id, actor="Tester", request_key="notfound-managed-analysis"), helper.db)["id"]
        # The reusable seed originally contains one target; this test adds another.
        helper.db.get(RadiusAnalysis, helper.item_id).total_rows = 2
        helper.db.commit()
        yield helper
    finally:
        helper.tearDown()


@pytest.mark.parametrize("stage", ["analysis", "search"])
def test_not_found_pause_finishes_row_and_restores_without_duplicates(managed_not_found, stage):
    helper = managed_not_found
    if stage == "search":
        helper.analyze()
    entered, release = Event(), Event()
    errors = []
    original = nearest_eligible if stage == "analysis" else run_correction_matching
    target = "app.modules.corrections.radius_analysis.nearest_eligible" if stage == "analysis" else "app.modules.corrections.progress.run_correction_matching"

    def blocked(*args, **kwargs):
        entered.set()
        if not release.wait(10):
            raise RuntimeError("Test did not release active row")
        return original(*args, **kwargs)

    def pause():
        try:
            with Session(helper.engine) as db:
                if stage == "analysis":
                    analysis_job(helper.item_id, JobRequest(state="paused"), db)
                else:
                    search_job(helper.item_id, SearchJobRequest(state="paused"), db)
        except Exception as exc:
            errors.append(exc)

    with patch(target, side_effect=blocked):
        if stage == "analysis":
            analysis_job(helper.item_id, JobRequest(state="running"), helper.db)
        else:
            helper.search()
        try:
            assert entered.wait(10)
            control = Thread(target=pause)
            helper.threads.append(control)
            control.start()
            helper.until(lambda value: value["activity"]["operation"] == "pausing")
            assert control.is_alive()
        finally:
            release.set()
        control.join(10)
    assert errors == []
    paused = helper.read()
    assert paused[stage]["state"] == "paused" and paused[stage]["processed_rows"] == 1
    assert not paused["activity"]["active"]
    helper.db.close()
    helper.db = Session(helper.engine)
    assert helper.read()[stage]["processed_rows"] == 1
    if stage == "analysis":
        helper.analyze()
        assert helper.db.query(RadiusAnalysisRow).filter_by(analysis_id=helper.item_id).count() == 2
    else:
        helper.search()
        helper.until(lambda value: value["search"]["status"] == "completed")
        assert helper.db.query(CorrectionTarget).count() == 2
        assert helper.db.query(CorrectionCandidateEvidence).count() == 2
