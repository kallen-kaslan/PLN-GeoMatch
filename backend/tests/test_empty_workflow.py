"""Live workflow checks on temporary SQLite files; never import app.main."""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests import test_radius_analysis as fixtures
from app.models.upload import SourceRecord, UploadBatch, DatasetType, BatchStatus
from app.models.pdpj import PdpjReview
from app.models.upload_file import UploadFileArchive, UploadSheetImport  # noqa: F401
from app.models.coordinate_repair import CoordinateRepair  # noqa: F401
from app.models.master_summary import MasterSummaryCache  # noqa: F401
from app.models.radius_analysis import RadiusAnalysis, RadiusAnalysisRow
from app.models.matching import MatchingRun, MatchCandidate, ReconciliationProcess
from app.models.correction import CorrectionTarget, CorrectionCandidateEvidence
from app.modules.corrections import empty_jobs
from app.modules.corrections.radius_analysis import nearest_eligible
from app.modules.corrections.radius_router import start, StartAnalysis, analysis_job, search_job, JobRequest, SearchJobRequest, restore_workflow
from app.modules.corrections.workflow import pending
from app.sqlite_runtime import configure_sqlite_engine


class EmptyWorkflowTests(unittest.TestCase):
    def setUp(self):
        seed = fixtures.RadiusTests()
        seed.setUp()
        self.batch_id, self.review_id = seed.batch.id, seed.fixture.review.id
        self.target_id = seed.target.id
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "workflow.db"
        destination = sqlite3.connect(self.path)
        seed.db.connection().connection.driver_connection.backup(destination)
        destination.close()
        seed.tearDown()
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}", connect_args={"check_same_thread": False})
        configure_sqlite_engine(self.engine)
        self.db = Session(self.engine)
        self.threads = []
        def launch(bind, identity, kind):
            thread = Thread(target=empty_jobs.work, args=(bind, identity, kind), daemon=True)
            self.threads.append(thread)
            thread.start()
        self.launch_patch = patch.object(empty_jobs, "launch", side_effect=launch)
        self.launch_patch.start()
        self.item_id = start(StartAnalysis(batch_id=self.batch_id, actor="Tester", request_key="workflow-analysis-key"), self.db)["id"]

    def tearDown(self):
        self.launch_patch.stop()
        for thread in self.threads:
            thread.join(10)
        self.db.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def read(self, radius=None):
        self.db.rollback()
        self.db.expire_all()
        return restore_workflow(self.batch_id, radius, self.db)

    def until(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.read()
            if predicate(value):
                return value
            time.sleep(0.02)
        self.fail(f"Timed out: {self.read()}")

    def analyze(self):
        analysis_job(self.item_id, JobRequest(state="running"), self.db)
        return self.until(lambda value: value["analysis"]["state"] == "ready" and not value["activity"]["active"])

    def search(self, radius=35):
        return search_job(self.item_id, SearchJobRequest(state="running", radius_meters=radius, request_key="workflow-search-key"), self.db)

    def more_targets(self):
        for number, data in [(3, {"lat": -6.2, "lon": 106.8}), (4, {"lat": 95, "lon": 106.8})]:
            self.db.add(SourceRecord(batch_id=self.batch_id, row_number=number, data=data))
        item = self.db.get(RadiusAnalysis, self.item_id)
        item.total_rows = 3
        self.db.commit()

    def test_server_finishes_without_browser_advances_and_preserves_exclusions(self):
        from itertools import count

        # Windows clock granularity can round tiny in-memory chunks to zero.
        # Use a deterministic clock to verify duration accumulation and storage.
        clock = count(step=0.01)
        self.more_targets()
        analyzed = self.analyze()
        self.assertEqual(analyzed["analysis"]["recommended_radius_meters"], 35)
        self.assertEqual(analyzed["analysis"]["coordinate_rows"], 1)
        self.assertEqual(self.read(35)["analysis"]["coverage_rows"], 2)
        self.assertEqual(self.read(30)["analysis"]["coverage_rows"], 0)
        # Choosing a radius must never rebuild Master Sisa or observations.
        with patch("app.modules.corrections.progress.monotonic", side_effect=clock.__next__), patch("app.modules.corrections.progress.advance_preparation", side_effect=AssertionError("prepared twice")), patch("app.modules.corrections.progress.advance_observations", side_effect=AssertionError("indexed twice")):
            self.search()
            result = self.until(lambda value: value["search"] is not None and value["search"]["status"] == "completed")
        job = result["search"]
        self.assertEqual((job["processed_rows"], job["matched_rows"], job["coordinate_rows"], job["no_candidate_rows"]), (3, 2, 1, 0))
        self.assertGreater(job["elapsed_seconds"], 0)
        candidates = self.db.query(MatchCandidate).all()
        self.assertEqual(len(candidates), 2)
        self.assertEqual({row.candidate_idpel for row in candidates}, {"533111000002"})
        self.assertEqual(self.db.query(CorrectionCandidateEvidence).count(), 2)
        prepared = self.db.get(ReconciliationProcess, self.db.get(RadiusAnalysis, self.item_id).process_id)
        actual = self.db.get(ReconciliationProcess, job["process_id"])
        self.assertEqual(actual.master_snapshot_id, prepared.master_snapshot_id)
        self.assertEqual(actual.source_batches, prepared.source_batches)
        self.search()
        self.until(lambda value: not value["activity"]["active"])
        self.assertEqual(self.db.query(MatchingRun).count(), 1)
        self.assertEqual(self.db.query(CorrectionTarget).count(), 3)
        self.assertNotIn(self.batch_id, {row["batch_id"] for row in pending(self.db)})

    def test_pause_waits_for_active_analysis_row_then_resumes_without_duplicates(self):
        self.more_targets()
        entered, release = Event(), Event()
        pause_errors = []
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test did not release row")
            return nearest_eligible(*args, **kwargs)
        def pause():
            try:
                with Session(self.engine) as db:
                    analysis_job(self.item_id, JobRequest(state="paused"), db)
            except Exception as exc:
                pause_errors.append(exc)
        with patch("app.modules.corrections.radius_analysis.nearest_eligible", side_effect=blocked):
            analysis_job(self.item_id, JobRequest(state="running"), self.db)
            self.assertTrue(entered.wait(5))
            control = Thread(target=pause)
            self.threads.append(control)
            control.start()
            try:
                self.until(lambda value: value["activity"]["operation"] == "pausing")
                self.assertTrue(control.is_alive())
            finally:
                release.set()
            control.join(5)
        self.assertEqual(pause_errors, [])
        paused = self.read()
        self.assertEqual(paused["analysis"]["state"], "paused")
        self.assertEqual(paused["analysis"]["processed_rows"], 1)
        self.assertFalse(paused["activity"]["active"])
        # Simulate a server exit after a committed row while state still says
        # running. Reading must not restart it or discard the checkpoint.
        self.db.get(RadiusAnalysis, self.item_id).state = "running"
        self.db.commit()
        self.db.close()
        self.db = Session(self.engine)
        self.assertEqual(self.read()["analysis"]["processed_rows"], 1)
        self.assertFalse(self.read()["activity"]["active"])
        self.analyze()
        self.assertEqual(self.db.query(RadiusAnalysisRow).count(), 3)

    def test_pause_during_candidate_row_preserves_atomic_outcome_and_evidence(self):
        self.more_targets()
        self.analyze()
        from app.modules.corrections.engine import run_correction_matching
        entered, release = Event(), Event()
        errors = []
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test did not release search row")
            return run_correction_matching(*args, **kwargs)
        def pause():
            try:
                with Session(self.engine) as db:
                    search_job(self.item_id, SearchJobRequest(state="paused"), db)
            except Exception as exc:
                errors.append(exc)
        with patch("app.modules.corrections.progress.run_correction_matching", side_effect=blocked):
            self.search()
            self.assertTrue(entered.wait(5))
            control = Thread(target=pause)
            self.threads.append(control)
            control.start()
            try:
                self.until(lambda value: value["activity"]["operation"] == "pausing")
                self.assertTrue(control.is_alive())
            finally:
                release.set()
            control.join(5)
        self.assertEqual(errors, [])
        paused = self.read()
        self.assertEqual(paused["search"]["state"], "paused")
        self.assertEqual(paused["search"]["processed_rows"], 1)
        self.assertEqual(self.db.query(CorrectionTarget).count(), 1)
        self.assertEqual(self.db.query(MatchCandidate).count(), 1)
        self.assertEqual(self.db.query(CorrectionCandidateEvidence).count(), 1)
        task = next(row for row in pending(self.db) if row["batch_id"] == self.batch_id)
        self.assertEqual(task["analysis_id"], self.item_id)
        self.search()
        self.until(lambda value: value["search"]["status"] == "completed")
        self.assertEqual(self.db.query(CorrectionTarget).count(), 3)
        self.assertEqual(self.db.query(MatchCandidate).count(), 2)

    def test_radius_below_recommendation_produces_real_no_candidate_count(self):
        self.analyze()
        self.search(5)
        result = self.until(lambda value: value["search"] and value["search"]["status"] == "completed")
        self.assertEqual(result["search"]["no_candidate_rows"], 1)
        self.assertEqual(result["search"]["matched_rows"], 0)
        self.assertEqual(self.db.query(MatchCandidate).count(), 0)

    def test_multiple_observations_group_by_idpel_and_every_pdpj_observation_is_excluded(self):
        master_id = self.db.get(PdpjReview, self.review_id).master_batch_ids[0]
        master = self.db.get(UploadBatch, master_id)
        for number, identity, lat in [(4, "533111000001", -6.20001), (5, "533111000002", -6.2001), (6, "533111000003", -6.2004)]:
            fields = {"idpel": identity, "lat": lat, "lon": 106.8}
            self.db.add(SourceRecord(batch_id=master_id, row_number=number, data=fields, idpel=identity, is_valid=True, normalized_data=fields))
        master.total_rows = 5
        self.db.commit()
        self.analyze()
        self.assertEqual(self.read()["analysis"]["recommended_radius_meters"], 15)
        self.search(50)
        self.until(lambda value: value["search"]["status"] == "completed")
        rows = self.db.query(MatchCandidate).order_by(MatchCandidate.rank).all()
        self.assertEqual([row.candidate_idpel for row in rows], ["533111000002", "533111000003"])
        self.assertLess(rows[0].distance_meters, 12)
        self.assertEqual(self.db.query(CorrectionCandidateEvidence).count(), 2)

    def test_new_master_and_pdpj_do_not_change_pinned_search_or_old_radius(self):
        self.analyze()
        original = self.read()
        newer = UploadBatch(filename="new-master.csv", dataset_type=DatasetType.DIL, status=BatchStatus.COMPLETED, catalog_version=3, total_rows=1)
        self.db.add(newer)
        self.db.flush()
        fields = {"idpel": "533111000099", "lat": -6.2, "lon": 106.8}
        self.db.add(SourceRecord(batch_id=newer.id, row_number=2, data=fields, normalized_data=fields, is_valid=True, idpel=fields["idpel"]))
        old_review = self.db.get(PdpjReview, self.review_id)
        self.db.add(PdpjReview(batch_id=old_review.batch_id, status="completed", master_batch_ids=[newer.id]))
        self.db.commit()
        self.search(35)
        result = self.until(lambda value: value["search"]["status"] == "completed")
        self.assertEqual(result["analysis"]["pdpj_review_id"], original["analysis"]["pdpj_review_id"])
        self.assertEqual(self.db.query(MatchCandidate).one().candidate_idpel, "533111000002")
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            self.search(100)
        self.assertEqual(self.read()["search"]["radius_meters"], 35)

    def test_failed_candidate_row_rolls_back_only_active_row_and_can_resume(self):
        self.more_targets()
        self.analyze()
        from app.modules.corrections.writer import SearchWriter
        original = SearchWriter.flush
        calls = 0
        def fail_second(writer):
            nonlocal calls
            calls += 1
            original(writer)
            if calls == 2:
                raise RuntimeError("failure after evidence insert, before commit")
        with self.assertLogs(empty_jobs.logger, level="ERROR"), patch.object(SearchWriter, "flush", fail_second):
            self.search()
            result = self.until(lambda value: value["search"] and value["search"]["state"] == "failed")
            self.until(lambda value: not value["activity"]["active"])
        self.assertEqual(result["search"]["processed_rows"], 1)
        self.assertEqual(self.db.query(CorrectionTarget).count(), 1)
        self.assertEqual(self.db.query(MatchCandidate).count(), 1)
        self.assertEqual(self.db.query(CorrectionCandidateEvidence).count(), 1)
        self.search()
        self.until(lambda value: value["search"]["status"] == "completed")
        self.assertEqual(self.db.query(CorrectionTarget).count(), 3)
        self.assertEqual(self.db.query(MatchCandidate).count(), 2)

    def test_pending_new_analysis_is_not_hidden_by_previous_completed_search(self):
        self.analyze()
        self.search()
        self.until(lambda value: value["search"]["status"] == "completed")
        review = self.db.get(PdpjReview, self.review_id)
        self.db.add(PdpjReview(batch_id=review.batch_id, status="completed", master_batch_ids=review.master_batch_ids))
        self.db.commit()
        second = start(StartAnalysis(batch_id=self.batch_id, actor="Tester", request_key="new-analysis-key"), self.db)
        self.assertNotEqual(second["id"], self.item_id)
        task = next(item for item in pending(self.db) if item["batch_id"] == self.batch_id)
        self.assertEqual(task["analysis_id"], second["id"])
        self.assertEqual(task["stage"], "analysis")
        retained = restore_workflow(self.batch_id, None, self.db, analysis_id=self.item_id)
        self.assertEqual(retained["analysis"]["id"], self.item_id)
        self.assertEqual(retained["search"]["radius_meters"], 35)
        self.assertEqual(retained["search"]["status"], "completed")

    def test_category_error_is_not_counted_as_a_coordinate_error(self):
        target = self.db.get(SourceRecord, self.target_id)
        target.data = {"idpel": "533111000009", "lat": -6.2, "lon": 106.8}
        self.db.commit()
        value = self.analyze()["analysis"]
        self.assertEqual((value["invalid_rows"], value["coordinate_rows"], value["category_rows"]), (1, 0, 1))
        self.search(35)
        job = self.until(lambda value: value["search"]["status"] == "completed")["search"]
        self.assertEqual((job["coordinate_rows"], job["other_issue_rows"], job["no_candidate_rows"]), (0, 1, 0))

    def test_archived_upload_is_idempotent_and_raw_preview_does_not_transform_cells(self):
        from io import BytesIO
        from starlette.datastructures import UploadFile
        from app.config import settings
        from app.modules.upload.archive import store_file, preview_original_table, import_sheet, SheetRequest
        from app.modules.upload.router import apply_mapping, MappingRequest
        from app.modules.upload.progress import UploadProgress
        with patch.object(settings, "UPLOAD_STORAGE_DIR", str(Path(self.tmp.name) / "uploads")):
            content = b"noagenda,latitudey,longitude,nokwhmeter,daya\n001,-6.2,106.8,000123,bukanangka\n"
            archive = store_file(UploadFile(BytesIO(content), filename="empty.csv"), self.db, UploadProgress(None))
            duplicate = store_file(UploadFile(BytesIO(content), filename="empty.csv"), self.db, UploadProgress(None))
            self.assertEqual(archive["id"], duplicate["id"])
            table = preview_original_table(archive["id"], self.db, None)
            self.assertEqual(table["headers"], ["noagenda", "latitudey", "longitude", "nokwhmeter", "daya"])
            self.assertEqual(table["rows"][0][0], "001")
            request = SheetRequest(dataset_type=DatasetType.IDPEL_KOSONG)
            imported = import_sheet(archive["id"], request, self.db, UploadProgress(None))
            self.assertEqual(import_sheet(archive["id"], request, self.db, UploadProgress(None))["id"], imported["id"])
            mapped = apply_mapping(MappingRequest(batch_id=imported["id"], column_mapping={"lat": "latitudey", "lon": "longitude", "agenda_ref": "noagenda", "nomor_meter_kwh": "nokwhmeter"}), self.db)
            self.assertEqual(mapped["rows"], 1)
            self.assertEqual(self.db.get(UploadBatch, imported["id"]).status, BatchStatus.COMPLETED)
            self.batch_id = imported["id"]
            self.item_id = start(StartAnalysis(batch_id=self.batch_id, actor="Tester", request_key="uploaded-analysis-key"), self.db)["id"]
            self.analyze()
            self.search()
            result = self.until(lambda value: value["search"] and value["search"]["status"] == "completed")
            self.assertEqual(result["search"]["matched_rows"], 1)
            outcome = self.db.query(CorrectionTarget).one()
            self.assertEqual(outcome.fields["agenda_ref"], "001")
            self.assertEqual(outcome.fields["nomor_meter_kwh"], "000123")

    def test_existing_not_found_workflow_keeps_identity_conflict_rules(self):
        from app.modules.corrections.service import create_check, CorrectionKind
        from app.modules.corrections.progress import advance_progress
        batch = UploadBatch(filename="not-found.csv", dataset_type=DatasetType.IDPEL_TIDAK_KETEMU, status=BatchStatus.COMPLETED, total_rows=2)
        self.db.add(batch)
        self.db.flush()
        for number, identity in enumerate(["533111009999", "533111000001"], 2):
            self.db.add(SourceRecord(batch_id=batch.id, row_number=number, data={"idpel": identity, "lat": -6.2, "lon": 106.8}))
        self.db.commit()
        process, run, _ = create_check(self.db, CorrectionKind.NOT_FOUND, batch.id, self.review_id, 100, "old-kind-request", "Tester", incremental=True)
        for _ in range(30):
            if run.status.value == "completed":
                break
            run = advance_progress(self.db, CorrectionKind.NOT_FOUND, process.id, run.id, run.processing["revision"], 1)
        self.assertEqual(run.status.value, "completed")
        rows = self.db.query(CorrectionTarget).filter_by(run_id=run.id).order_by(CorrectionTarget.source_record_id).all()
        self.assertEqual([row.search_status for row in rows], ["matched", "pdpj_conflict"])
        self.assertEqual(self.db.query(MatchCandidate).one().candidate_idpel, "533111000002")

    def test_http_workflow_routes_restore_real_data_and_validate_radius(self):
        import asyncio
        import json
        from fastapi import FastAPI
        from app.database import get_db
        from app.modules.corrections.radius_router import router
        app = FastAPI()
        app.include_router(router, prefix="/corrections")
        def session():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_db] = session
        async def call(method, path, body=None, query=b""):
            messages = []
            async def receive():
                return {"type": "http.request", "body": json.dumps(body or {}).encode(), "more_body": False}
            async def send(message):
                messages.append(message)
            await app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "", "query_string": query, "headers": [(b"content-type", b"application/json")], "server": ("test", 80), "client": ("test", 1)}, receive, send)
            code = next(message["status"] for message in messages if message["type"] == "http.response.start")
            payload = json.loads(b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body"))
            return code, payload
        base = "/corrections/idpel_kosong/radius-analyses"
        code, value = asyncio.run(call("GET", f"{base}/workflow", query=f"batch_id={self.batch_id}".encode()))
        self.assertEqual(code, 200)
        self.assertEqual(value["analysis"]["processed_rows"], 0)
        self.assertFalse(value["activity"]["active"])
        self.assertEqual(asyncio.run(call("POST", f"{base}/{self.item_id}/analysis-job", {"state": "running"}))[0], 200)
        self.until(lambda value: value["analysis"]["state"] == "ready" and not value["activity"]["active"])
        self.assertEqual(asyncio.run(call("POST", f"{base}/{self.item_id}/search-job", {"state": "running", "radius_meters": 0, "request_key": "http-search-key"}))[0], 422)
        self.assertEqual(asyncio.run(call("POST", f"{base}/{self.item_id}/search-job", {"state": "running", "radius_meters": 35, "request_key": "http-search-key"}))[0], 200)
        self.until(lambda value: value["search"] and value["search"]["status"] == "completed")
        code, value = asyncio.run(call("GET", f"{base}/workflow", query=f"batch_id={self.batch_id}&analysis_id={self.item_id}&radius_meters=35".encode()))
        self.assertEqual(code, 200)
        self.assertEqual(value["search"]["matched_rows"], 1)
        self.assertEqual(value["analysis"]["coverage_rows"], 1)
        self.assertEqual(asyncio.run(call("GET", f"{base}/workflow", query=f"batch_id={self.batch_id + 1}&analysis_id={self.item_id}".encode()))[0], 404)

    def test_transient_status_lock_does_not_abandon_a_started_worker(self):
        from app.processing_activity import activity_lock
        item = self.db.get(RadiusAnalysis, self.item_id)
        item.progress = {"managed": True, "job_kind": "analysis"}
        self.db.commit()
        with activity_lock(self.db, empty_jobs.SCOPE, self.item_id, "observing"):
            worker = Thread(target=empty_jobs.work, args=(self.engine, self.item_id, "analysis"))
            self.threads.append(worker)
            worker.start()
            time.sleep(0.08)
            self.assertTrue(worker.is_alive())
        value = self.until(lambda value: value["analysis"]["state"] == "ready")
        self.assertEqual(value["analysis"]["processed_rows"], 1)
        self.assertEqual(self.db.query(RadiusAnalysisRow).count(), 1)

    def test_second_upload_reuses_the_same_prepared_exclusion_and_observation_index(self):
        self.analyze()
        first = self.db.get(ReconciliationProcess, self.db.get(RadiusAnalysis, self.item_id).process_id)
        snapshot = first.master_snapshot_id
        batch = UploadBatch(filename="second-empty.csv", dataset_type=DatasetType.IDPEL_KOSONG, status=BatchStatus.COMPLETED, total_rows=1)
        self.db.add(batch)
        self.db.flush()
        self.db.add(SourceRecord(batch_id=batch.id, row_number=2, data={"lat": -6.2, "lon": 106.8}))
        self.db.commit()
        self.batch_id = batch.id
        self.item_id = start(StartAnalysis(batch_id=batch.id, actor="Tester", request_key="second-upload-analysis"), self.db)["id"]
        with patch("app.modules.spatial.master_preparation.read_source_chunk", side_effect=AssertionError("master sources scanned twice")):
            self.analyze()
        second = self.db.get(ReconciliationProcess, self.db.get(RadiusAnalysis, self.item_id).process_id)
        self.assertEqual(second.master_snapshot_id, snapshot)

    def test_reset_rejects_an_active_worker_and_handles_radius_foreign_keys_when_idle(self):
        from fastapi import HTTPException
        from app.processing_activity import activity_lock
        from app.modules.upload.router import reset_database
        self.analyze()
        with activity_lock(self.db, empty_jobs.SCOPE, self.item_id, "analysis"):
            with self.assertRaises(HTTPException) as rejected:
                reset_database(self.db)
            self.assertEqual(rejected.exception.status_code, 409)
            self.db.rollback()
            self.assertEqual(self.db.query(RadiusAnalysisRow).count(), 1)
        # Isolated temporary DB only; no archived files point outside the test.
        reset_database(self.db)
        self.assertEqual(self.db.query(RadiusAnalysis).count(), 0)
        self.assertEqual(self.db.query(SourceRecord).count(), 0)


if __name__ == "__main__":
    unittest.main()
