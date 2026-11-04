"""Phase 3 regression checks; SQLite memory only, no application startup."""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import unittest
import asyncio
import json
from unittest.mock import patch
from sqlalchemy.orm import Session
from fastapi import HTTPException
from tests import test_empty_correction_overview as fixtures
from app.models.upload import UploadBatch, SourceRecord, DatasetType, BatchStatus
from app.models.pdpj import PdpjRow
from app.models.matching import ReconciliationProcess, MatchingRun
from app.models.master_sisa import MasterSisaRecord, CorrectionMasterObservation
from app.models.radius_analysis import RadiusAnalysis, RadiusAnalysisRow
from app.models.correction import CorrectionTarget
from app.modules.corrections.radius_analysis import create_analysis, advance_analysis, analysis_info, nearest_eligible, automatic_review
from app.modules.corrections.radius_router import control, StateRequest, save_radius, RadiusRequest, search, SearchRequest
from app.modules.corrections.radius_router import router, StartAnalysis, start
from app.models.pdpj import PdpjReview
from app.database import get_db
from app.modules.corrections.workflow import pending
from app.modules.corrections.progress import advance_progress
from app.modules.corrections.service import CorrectionKind
from app.modules.corrections.empty_rules import target_errors
from app.modules.upload.normalization import extract_standard_fields, validate_fields


class RadiusTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EmptyOverviewTests()
        self.fixture.setUp()
        self.db = self.fixture.db
        self.batch = self.fixture.batches[0]
        self.target = self.fixture.a
        self.target.data = {"latitudey": -6.2, "longitude": 106.8, "daya": "bukan angka"}
        self.batch.total_rows = 1
        self.master = UploadBatch(filename="master.csv", dataset_type=DatasetType.DIL, status=BatchStatus.COMPLETED, catalog_version=3, total_rows=2)
        self.db.add(self.master)
        self.db.flush()
        self.sources = []
        for idpel, lat in [("533111000001", -6.2), ("533111000002", -6.2003)]:
            row = SourceRecord(batch_id=self.master.id, row_number=len(self.sources)+2, data={"idpel": idpel, "lat": lat, "lon": 106.8}, idpel=idpel, is_valid=True, normalized_data={"idpel": idpel, "lat": lat, "lon": 106.8})
            self.db.add(row)
            self.sources.append(row)
        review = self.fixture.review
        review.status = "completed"
        review.master_batch_ids = [self.master.id]
        row = SourceRecord(batch_id=review.batch_id, row_number=2, data={})
        self.db.add(row)
        self.db.flush()
        self.db.add(PdpjRow(review_id=review.id, source_record_id=row.id, row_number=2, original_fields={}, current_fields={"idpel": "533111000001"}, existence="found"))
        self.db.commit()

    def tearDown(self):
        self.fixture.tearDown()

    def start(self):
        return create_analysis(self.db, self.batch.id, self.fixture.review.id, "Tester", "analysis-test-key")

    def finish(self, item):
        for _ in range(40):
            if item.state == "ready":
                return item
            item = advance_analysis(self.db, item.id, item.revision, chunk_size=1)
        self.fail(f"Analysis did not finish: {item.stage} {item.progress}")

    def test_real_preparation_excludes_pdpj_and_rounds_up_then_reuses_coverage(self):
        item = self.finish(self.start())
        result = analysis_info(self.db, item, 30)
        self.assertEqual(result["recommended_radius_meters"], 35)
        self.assertEqual(result["coverage_rows"], 0)
        self.assertEqual(analysis_info(self.db, item, 35)["coverage_rows"], 1)
        row = self.db.query(RadiusAnalysisRow).one()
        self.assertEqual(row.candidate_idpel, "533111000002")
        self.assertEqual(self.db.query(MasterSisaRecord).count(), 1)
        self.assertEqual(self.db.query(CorrectionMasterObservation).count(), 1)
        self.assertEqual(self.db.query(MatchingRun).count(), 0)
        self.assertEqual(self.start().id, item.id)

    def test_checkpoint_survives_session_reopen_pause_revision_and_no_duplicate_rows(self):
        item = self.start()
        while item.stage == "preparing":
            item = advance_analysis(self.db, item.id, item.revision)
        paused = control(item.id, StateRequest(revision=item.revision, state="paused"), self.db)
        with self.assertRaises(HTTPException):
            advance_analysis(self.db, item.id, paused["revision"])
        control(item.id, StateRequest(revision=paused["revision"], state="running"), self.db)
        analysis_id = item.id
        self.db.close()
        self.db = self.fixture.db = Session(self.fixture.engine)
        item = self.finish(self.db.get(RadiusAnalysis, analysis_id))
        self.assertEqual(item.processed_rows, 1)
        self.assertEqual(self.db.query(RadiusAnalysisRow).count(), 1)
        with self.assertRaises(HTTPException):
            advance_analysis(self.db, item.id, item.revision - 1)

    def test_invalid_outlier_and_precision_do_not_produce_false_full_recommendation(self):
        self.target.data = {"latitudey": -6.2003000001, "longitude": 106.8}
        for number, data in [(3, {"latitudey": 95, "longitude": 106}), (4, {"latitudey": 1, "longitude": 1})]:
            self.db.add(SourceRecord(batch_id=self.batch.id, row_number=number, data=data))
        self.db.commit()
        item = self.finish(self.start())
        result = analysis_info(self.db, item, 5)
        self.assertEqual(result["processed_rows"], 3)
        self.assertEqual(result["invalid_rows"], 1)
        self.assertEqual(result["outside_limit_rows"], 1)
        self.assertIsNone(result["recommended_radius_meters"])
        self.assertEqual(result["partial_radius_meters"], 5)
        self.assertEqual(result["coverage_rows"], 1)

    def test_saved_radius_and_search_are_idempotent_and_pin_same_snapshot(self):
        item = self.finish(self.start())
        saved = save_radius(item.id, RadiusRequest(revision=item.revision, radius_meters=35), self.db)
        request = SearchRequest(revision=saved["revision"], request_key="search-test-key")
        first = search(item.id, request, self.db)
        self.assertEqual(search(item.id, request, self.db), first)
        prepared = self.db.get(ReconciliationProcess, item.process_id)
        actual = self.db.get(ReconciliationProcess, first["process_id"])
        self.assertEqual(actual.master_snapshot_id, prepared.master_snapshot_id)
        self.assertEqual(actual.source_batches, prepared.source_batches)
        self.assertEqual(actual.radius_meters, 35)
        self.assertEqual(self.db.query(MatchingRun).count(), 1)
        task = next(task for task in pending(self.db) if task["batch_id"] == self.batch.id)
        self.assertEqual(task["stage"], "search")
        run = self.db.query(MatchingRun).one()
        for _ in range(15):
            if run.status.value == "completed":
                break
            run = advance_progress(self.db, CorrectionKind.EMPTY, actual.id, run.id, run.processing["revision"], 20)
        self.assertEqual(run.status.value, "completed")
        outcome = self.db.query(CorrectionTarget).one()
        self.assertEqual(outcome.search_status, "matched")
        self.assertEqual(outcome.candidate_count, 1)
        self.assertEqual(outcome.errors, [])

    def test_failed_chunk_rolls_back_and_resumes_from_last_saved_target(self):
        item = self.start()
        while item.stage == "preparing":
            item = advance_analysis(self.db, item.id, item.revision)
        with patch("app.modules.corrections.radius_analysis.nearest_eligible", side_effect=RuntimeError("interrupted")):
            with self.assertRaises(RuntimeError):
                advance_analysis(self.db, item.id, item.revision)
        self.assertEqual(item.state, "failed")
        self.assertEqual(item.processed_rows, 0)
        self.assertEqual(self.db.query(RadiusAnalysisRow).count(), 0)
        control(item.id, StateRequest(revision=item.revision, state="running"), self.db)
        self.assertEqual(self.finish(item).processed_rows, 1)

    def test_empty_rules_ignore_other_columns_but_preserve_coordinates_and_category(self):
        fields = extract_standard_fields(self.target.data)
        self.assertTrue(validate_fields(fields, DatasetType.IDPEL_KOSONG))
        self.assertEqual(target_errors(validate_fields(fields, DatasetType.IDPEL_KOSONG), DatasetType.IDPEL_KOSONG), [])
        fields = extract_standard_fields({"idpel": "533111000001", "lat": 95, "lon": 106})
        errors = target_errors(validate_fields(fields, DatasetType.IDPEL_KOSONG), DatasetType.IDPEL_KOSONG)
        self.assertEqual({error["field"] for error in errors}, {"idpel", "lat"})
        self.assertEqual(target_errors(errors, DatasetType.IDPEL_TIDAK_KETEMU), errors)

    def test_pending_recovers_ready_analysis_without_creating_search(self):
        item = self.finish(self.start())
        task = next(task for task in pending(self.db) if task["batch_id"] == self.batch.id)
        self.assertEqual(task["stage"], "radius")
        self.assertEqual(task["processed_rows"], 1)
        self.assertEqual(task["analysis_id"], item.id)
        self.assertEqual(self.db.query(MatchingRun).count(), 0)

    def test_start_resolves_pdpj_automatically_and_retry_keeps_original_sources(self):
        request = StartAnalysis(batch_id=self.batch.id, actor="Tester", request_key="automatic-test-key")
        result = start(request, self.db)
        self.assertEqual(result["pdpj_review_id"], self.fixture.review.id)
        self.db.add(PdpjReview(batch_id=self.fixture.review.batch_id, master_batch_ids=[self.master.id], status="completed"))
        self.db.commit()
        self.assertEqual(start(request, self.db)["id"], result["id"])
        self.assertEqual(start(request, self.db)["pdpj_review_id"], result["pdpj_review_id"])
        self.assertEqual(self.db.query(RadiusAnalysis).count(), 1)

    def test_automatic_review_requires_current_approved_version(self):
        self.assertEqual(automatic_review(self.db).id, self.fixture.review.id)
        working = PdpjReview(batch_id=self.fixture.review.batch_id, master_batch_ids=[self.master.id], status="in_progress")
        self.db.add(working)
        self.db.commit()
        with self.assertRaises(HTTPException) as failure:
            automatic_review(self.db)
        self.assertEqual(failure.exception.status_code, 409)
        published = PdpjReview(batch_id=working.batch_id, source_review_id=working.id, master_batch_ids=[self.master.id], status="completed")
        self.db.add(published)
        self.db.commit()
        self.assertEqual(automatic_review(self.db).id, published.id)

    def test_spherical_bounds_include_dateline(self):
        item = self.finish(self.start())
        process = self.db.get(ReconciliationProcess, item.process_id)
        observation = self.db.query(CorrectionMasterObservation).one()
        observation.latitude, observation.longitude = 0, -179.9999
        self.db.commit()
        found = nearest_eligible(self.db, process.master_snapshot_id, 0, 179.9999)
        self.assertIsNotNone(found)
        self.assertLess(found[0], 25)

    def test_http_restore_does_not_advance_and_rejects_invalid_radius(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/corrections")
        app.dependency_overrides[get_db] = lambda: self.db

        async def request(method, path, query=b"", body=None):
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
        code, value = asyncio.run(request("GET", base, f"batch_id={self.batch.id}".encode()))
        self.assertEqual((code, value), (200, None))
        item = self.start()
        code, value = asyncio.run(request("GET", f"{base}/{item.id}"))
        self.assertEqual(code, 200)
        self.assertEqual(value["processed_rows"], 0)
        self.assertEqual(self.db.query(RadiusAnalysisRow).count(), 0)
        self.assertEqual(asyncio.run(request("GET", f"{base}/{item.id}", b"radius_meters=NaN"))[0], 422)
        self.assertEqual(asyncio.run(request("PUT", f"{base}/{item.id}/radius", body={"revision": item.revision, "radius_meters": 0}))[0], 422)
        self.assertEqual(asyncio.run(request("POST", f"{base}/{item.id}/advance", body={"revision": item.revision + 1}))[0], 409)


if __name__ == "__main__":
    unittest.main()
