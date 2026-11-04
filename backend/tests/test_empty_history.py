"""Merged history removal preserves empty-ID checkpoints and shared sources."""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.models.radius_analysis import RadiusAnalysis, RadiusAnalysisRow
from app.models.upload import SourceRecord
from app.models.matching import ReconciliationProcess
from app.modules.corrections import empty_jobs
from app.modules.corrections.radius_router import search_job, SearchJobRequest
from app.modules.corrections.workflow import pending
from app.modules.history.deletion import delete_history
from app.processing_activity import activity_lock
from tests import test_empty_workflow as fixture


class EmptyHistoryTests(unittest.TestCase):
    setUp = fixture.EmptyWorkflowTests.setUp
    tearDown = fixture.EmptyWorkflowTests.tearDown
    read = fixture.EmptyWorkflowTests.read
    until = fixture.EmptyWorkflowTests.until
    analyze = fixture.EmptyWorkflowTests.analyze
    search = fixture.EmptyWorkflowTests.search
    more_targets = fixture.EmptyWorkflowTests.more_targets

    def paused_search(self):
        self.analyze()
        with patch.object(empty_jobs, "launch"):
            self.search()
        return search_job(self.item_id, SearchJobRequest(state="paused"), self.db)["search"]["process_id"]

    def test_deleting_finished_search_retains_analysis_and_can_restart(self):
        self.analyze()
        self.search()
        finished = self.until(lambda value: value["search"] and value["search"]["status"] == "completed" and not value["activity"]["active"])
        delete_history(self.db, finished["search"]["process_id"])
        self.db.commit()
        value = self.read()
        self.assertIsNone(value["search"])
        self.assertEqual(value["analysis"]["state"], "ready")
        self.assertEqual(self.db.query(RadiusAnalysisRow).count(), value["analysis"]["total_rows"])
        self.assertEqual(next(item for item in pending(self.db) if item["batch_id"] == self.batch_id)["stage"], "radius")
        result = search_job(self.item_id, SearchJobRequest(state="running", radius_meters=35, request_key="history-new-search-key"), self.db)
        self.assertIsNotNone(result["search"])
        self.until(lambda value: value["search"]["status"] == "completed" and not value["activity"]["active"])

    def test_deleting_paused_search_retains_import(self):
        process_id = self.paused_search()
        before = self.db.query(SourceRecord).count()
        delete_history(self.db, process_id)
        self.db.commit()
        self.assertIsNone(self.read()["search"])
        self.assertEqual(self.db.query(SourceRecord).count(), before)

    def test_preparation_cannot_be_removed_while_its_search_exists(self):
        process_id = self.paused_search()
        preparation = self.db.get(RadiusAnalysis, self.item_id).process_id
        with self.assertRaises(HTTPException) as raised:
            delete_history(self.db, preparation)
        self.assertEqual(raised.exception.status_code, 409)
        self.db.rollback()
        self.assertEqual(self.read()["search"]["process_id"], process_id)

    def test_clear_history_removes_radius_children_before_processes(self):
        self.paused_search()
        before = self.db.query(SourceRecord).count()
        delete_history(self.db)
        self.db.commit()
        self.assertEqual(self.db.query(RadiusAnalysisRow).count(), 0)
        self.assertEqual(self.db.query(RadiusAnalysis).count(), 0)
        self.assertEqual(self.db.query(ReconciliationProcess).count(), 0)
        self.assertEqual(self.db.query(SourceRecord).count(), before)
        self.assertEqual(next(item for item in pending(self.db) if item["batch_id"] == self.batch_id)["stage"], "analysis")

    def test_analysis_running_or_worker_active_blocks_history_deletion(self):
        preparation = self.db.get(RadiusAnalysis, self.item_id).process_id
        with self.assertRaises(HTTPException) as raised:
            delete_history(self.db, preparation)
        self.assertEqual(raised.exception.status_code, 409)
        self.db.rollback()
        self.analyze()
        with activity_lock(self.db, empty_jobs.SCOPE, self.item_id, "analysis"):
            with self.assertRaises(HTTPException) as raised:
                delete_history(self.db, preparation)
            self.assertEqual(raised.exception.status_code, 409)
            self.db.rollback()
        delete_history(self.db, preparation)
        self.db.commit()
        self.assertIsNone(self.db.get(RadiusAnalysis, self.item_id))


if __name__ == "__main__":
    unittest.main()
