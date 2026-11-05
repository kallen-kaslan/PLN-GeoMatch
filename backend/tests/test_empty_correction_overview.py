"""Run with python -B -m unittest tests.test_empty_correction_overview.

Uses only in-memory SQLite; does not import app.main or run startup migrations.
"""

import os
import asyncio
import json
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine, event, func, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.master_sisa import MasterSnapshot  # noqa: F401
from app.models.pdpj import PdpjReview
from app.models.correction import CorrectionCheck, CorrectionTarget
from app.models.correction_decision import CorrectionDecision
from app.models.matching import MatchCandidate, MatchingRun, ProcessStatus, ReconciliationProcess
from app.models.upload import BatchStatus, DatasetType, SourceRecord, UploadBatch
from app.modules.corrections.overview import overview_query, records, router, summary
from app.modules.corrections.workflow import pending, router as workflow_router


class EmptyOverviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.batches = []
        for kind, state in [
            (DatasetType.IDPEL_KOSONG, BatchStatus.COMPLETED),
            (DatasetType.IDPEL_KOSONG, BatchStatus.COMPLETED),
            (DatasetType.IDPEL_TIDAK_KETEMU, BatchStatus.COMPLETED),
            (DatasetType.IDPEL_KOSONG, BatchStatus.UPLOADED),
        ]:
            batch = UploadBatch(filename=f"file-{len(self.batches)}.csv", dataset_type=kind, status=state)
            self.db.add(batch)
            self.db.flush()
            self.batches.append(batch)
        self.a = self.source(0, "Alpha", "A_01")
        self.b = self.source(1, "Beta", "B02")
        self.source(2, "Other category", "C03")
        self.source(3, "Unconfirmed", "D04")
        pdpj = UploadBatch(filename="pdpj.csv", dataset_type=DatasetType.PDPJ, status=BatchStatus.COMPLETED)
        self.db.add(pdpj)
        self.db.flush()
        self.review = PdpjReview(batch_id=pdpj.id, master_batch_ids=[])
        self.db.add(self.review)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def source(self, index, name, agenda, lat=-6.2):
        fields = {"nama": name, "agenda_ref": agenda, "lat": lat, "lon": 106.8, "_normalization_version": 3}
        row = SourceRecord(batch_id=self.batches[index].id, row_number=2, data={}, normalized_data=fields)
        self.db.add(row)
        self.db.flush()
        return row

    def search(self, source, status="matched", generation=1, process=None):
        if process is None:
            process = ReconciliationProcess(process_name="Test", target_batch_id=source.batch_id)
            self.db.add(process)
            self.db.flush()
            self.db.add(CorrectionCheck(process_id=process.id, category="idpel_kosong", pdpj_review_id=self.review.id))
        run = MatchingRun(process_id=process.id, generation=generation, radius_meters=100)
        self.db.add(run)
        self.db.flush()
        if status is not None:
            self.db.add(CorrectionTarget(run_id=run.id, source_record_id=source.id, fields=source.normalized_data, identity_status="empty", search_status=status, candidate_count=2 if status == "matched" else 0))
        self.db.commit()
        return process, run

    def page(self, **kwargs):
        return records(db=self.db, q=kwargs.get("q", ""), status=kwargs.get("status", "all"), skip=kwargs.get("skip", 0), limit=kwargs.get("limit", 25))

    def choice(self, source, process, run, candidate_id):
        if candidate_id is not None and self.db.get(MatchCandidate, candidate_id) is None:
            self.db.add(MatchCandidate(id=candidate_id, process_id=process.id, generation=run.generation, target_record_id=source.id, target_ref="Test", target_lat=-6.2, target_lon=106.8, candidate_idpel="001234", candidate_lat=-6.2, candidate_lon=106.8, distance_meters=0))
            self.db.flush()
        event = CorrectionDecision(process_id=process.id, target_record_id=source.id, generation=run.generation, revision=1, candidate_id=candidate_id, request_key=f"choice_{source.id}", actor="Tester", reason="", target_fields=source.normalized_data, candidate={"fields": {"idpel": "001234"}})
        self.db.add(event)
        self.db.commit()
        return event

    def test_all_confirmed_imports_once_and_other_categories_excluded(self):
        page = self.page()
        self.assertEqual(page["total"], 2)
        self.assertEqual([row["id"] for row in page["items"]], [self.b.id, self.a.id])
        self.assertEqual(summary(self.db)["counts"], {"not_processed": 2})
        self.assertEqual(self.page(skip=1, limit=1)["items"][0]["id"], self.a.id)

    def test_partial_retry_preserves_previous_result_and_choice(self):
        process, old = self.search(self.a)
        self.db.add(MatchCandidate(id=123, process_id=process.id, target_record_id=self.a.id, target_ref="A", target_lat=-6.2, target_lon=106.8, candidate_idpel="001234", candidate_lat=-6.2, candidate_lon=106.8, distance_meters=0))
        self.db.commit()
        self.choice(self.a, process, old, 123)
        self.search(self.a, status=None, generation=2, process=process)
        row = self.page(status="candidates_found")["items"][0]
        self.assertEqual(row["generation"], 1)
        self.assertEqual(row["candidate_count"], 2)
        self.assertEqual(row["choice"]["idpel"], "001234")
        self.assertEqual(self.page(q="001234")["total"], 1)
        self.search(self.a, status="no_candidates", generation=3, process=process)
        self.assertEqual(self.page(status="no_candidates")["total"], 1)
        self.assertEqual(self.page(status="no_candidates")["items"][0]["choice"]["idpel"], "001234")
        self.assertEqual(self.page()["total"], 2)

    def test_search_statuses_coordinates_and_summary_partition(self):
        self.search(self.a)
        self.search(self.b, "pdpj_conflict")
        self.source(1, "Missing", "E05", lat=None)
        self.db.commit()
        counts = summary(self.db)["counts"]
        self.assertEqual(counts, {"candidates_found": 1, "not_processed": 1, "coordinate_issues": 1})
        self.assertEqual(sum(counts.values()), self.page()["total"])
        self.assertEqual(self.page(status="not_processed")["items"][0]["id"], self.b.id)
        self.assertEqual(self.page(q="alpha")["total"], 1)
        self.assertEqual(self.page(q="A_01")["total"], 1)
        self.assertEqual(self.page(q="%")["total"], 0)

    def test_latest_cancelled_choice_does_not_resurrect_old_choice(self):
        process, run = self.search(self.a)
        self.choice(self.a, process, run, 123)
        self.assertEqual(self.page(status="candidates_found")["total"], 1)
        self.assertIsNotNone(self.page(status="candidates_found")["items"][0]["choice"])
        self.db.add(CorrectionDecision(process_id=process.id, target_record_id=self.a.id, generation=run.generation, revision=2, candidate_id=None, request_key="cancel_choice", actor="Tester", reason="Cancel", target_fields=self.a.normalized_data, candidate={}))
        self.db.commit()
        self.assertEqual(self.page(status="candidates_found")["total"], 1)
        self.assertIsNone(self.page(status="candidates_found")["items"][0]["choice"])

    def test_unfinished_work_counts_only_rows_without_finished_search(self):
        self.search(self.a)
        pending = self.source(0, "Still running", "WAIT")
        self.db.commit()
        counts = summary(self.db)["counts"]
        self.assertEqual(counts, {"candidates_found": 1, "not_processed": 2})
        ids = {row["id"] for row in self.page(status="not_processed")["items"]}
        self.assertEqual(ids, {pending.id, self.b.id})

    def test_sqlite_summary_uses_batch_index_instead_of_scanning_all_master_rows(self):
        query, status, _ = overview_query(self.db, include_choices=False)
        statement = query.with_entities(status, func.count(SourceRecord.id)).group_by(status).statement
        sql = str(statement.compile(self.engine, compile_kwargs={"literal_binds": True}))
        plan = " ".join(row[3] for row in self.db.execute(text("EXPLAIN QUERY PLAN " + sql)))
        self.assertIn("SEARCH source_records", plan)
        self.assertNotIn("SCAN source_records", plan)

    def test_summary_avoids_decision_history_and_refreshes_after_new_results(self):
        statements = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            self.assertEqual(summary(self.db)["counts"], {"not_processed": 2})
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertEqual(len(statements), 1)
        self.assertNotIn("correction_decisions", statements[0].lower())
        self.search(self.a)
        self.assertEqual(summary(self.db)["counts"], {"candidates_found": 1, "not_processed": 1})
        self.search(self.a, "no_candidates")
        self.assertEqual(summary(self.db)["counts"], {"no_candidates": 1, "not_processed": 1})

    def test_http_routes_and_invalid_filters(self):
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/corrections")
        app.include_router(workflow_router, prefix="/corrections")
        app.dependency_overrides[get_db] = lambda: self.db

        async def get(path, query=b""):
            messages = []

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                messages.append(message)

            await app({
                "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "method": "GET", "scheme": "http", "path": path,
                "raw_path": path.encode(), "root_path": "", "query_string": query,
                "headers": [], "server": ("test", 80), "client": ("test", 1234),
            }, receive, send)
            code = next(item["status"] for item in messages if item["type"] == "http.response.start")
            payload = json.loads(b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body"))
            return code, payload

        base = "/corrections/idpel_kosong/overview"
        code, payload = asyncio.run(get(f"{base}/summary"))
        self.assertEqual(code, 200)
        self.assertEqual(payload["total_rows"], 2)
        code, payload = asyncio.run(get(f"{base}/records", b"q=Beta"))
        self.assertEqual(code, 200)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(asyncio.run(get(f"{base}/records", b"status=unknown"))[0], 422)
        self.assertEqual(asyncio.run(get(f"{base}/records", b"limit=101"))[0], 422)
        code, payload = asyncio.run(get("/corrections/idpel_kosong/workflow/pending"))
        self.assertEqual(code, 200)
        self.assertEqual(len(payload), 3)

    def test_upload_stage_is_recovered_from_database_without_browser_state(self):
        before = self.db.query(UploadBatch).count()
        items = {item["batch_id"]: item for item in pending(self.db)}
        self.assertEqual(len(items), 3)
        self.assertEqual(items[self.a.batch_id]["stage"], "analysis")
        draft = self.batches[3]
        self.assertEqual(items[draft.id]["stage"], "upload")
        draft.status = BatchStatus.COMPLETED
        draft.total_rows = 15
        draft_id = draft.id
        self.db.commit()
        self.db.close()
        self.db = Session(self.engine)
        restored = {item["batch_id"]: item for item in pending(self.db)}
        self.assertEqual(restored[draft_id]["stage"], "analysis")
        self.assertEqual(restored[draft_id]["total_rows"], 15)
        self.assertEqual(self.db.query(UploadBatch).count(), before)

    def test_pending_search_uses_latest_attempt_even_without_any_outcomes(self):
        process, first = self.search(self.a)
        first.status = ProcessStatus.COMPLETED
        self.db.commit()
        self.assertNotIn(self.a.batch_id, {item["batch_id"] for item in pending(self.db)})
        _, retry = self.search(self.a, status=None, generation=2, process=process)
        retry.processing = {"state": "paused", "stage": "matching", "processed_rows": 7, "total_rows": 20}
        self.db.commit()
        items = {item["batch_id"]: item for item in pending(self.db)}
        self.assertEqual(items[self.a.batch_id]["stage"], "search")
        self.assertEqual(items[self.a.batch_id]["state"], "paused")
        self.assertEqual(items[self.a.batch_id]["processed_rows"], 7)
        self.assertEqual(items[self.a.batch_id]["process_id"], process.id)
        retry.status = ProcessStatus.FAILED
        retry.processing = {**retry.processing, "state": "failed"}
        self.db.commit()
        self.assertEqual(next(item for item in pending(self.db) if item["batch_id"] == self.a.batch_id)["state"], "failed")


if __name__ == "__main__":
    unittest.main()
