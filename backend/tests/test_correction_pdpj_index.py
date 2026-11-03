"""Optimized chunks must preserve full-search candidates, conflicts, and evidence."""

from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.matching import MatchCandidate
from app.models.pdpj import PdpjReview, PdpjRow
from app.models.upload import SourceRecord, UploadBatch
from app.modules.corrections import pdpj_index
from app.modules.upload.normalization import extract_standard_fields
from tests import test_corrections as corrections
from tests import test_pdpj_publications as publications
from tests.test_corrections import check, upload
from tests.test_pdpj_progress import step
from tests.test_pdpj_validation import action, rows

reference = corrections.reference
partial = publications.partial


def snapshot(db: Session, run_id: int, process: int, generation: int) -> dict[str, Any]:
    return {
        "outcomes": [
            (
                row.source_record_id,
                row.fields,
                row.identity_status,
                row.search_status,
                row.candidate_count,
                row.errors,
                row.conflicts,
                row.warnings,
            )
            for row in db.query(CorrectionTarget)
            .filter_by(run_id=run_id)
            .order_by(CorrectionTarget.source_record_id)
        ],
        "candidates": [
            (
                row.target_record_id,
                row.candidate_idpel,
                row.candidate_lat,
                row.candidate_lon,
                row.distance_meters,
                row.rank,
                row.is_under_5m,
                evidence.fields,
                evidence.observations,
            )
            for row, evidence in db.query(MatchCandidate, CorrectionCandidateEvidence)
            .join(
                CorrectionCandidateEvidence,
                CorrectionCandidateEvidence.candidate_id == MatchCandidate.id,
            )
            .filter(
                MatchCandidate.process_id == process,
                MatchCandidate.generation == generation,
            )
            .order_by(MatchCandidate.target_record_id, MatchCandidate.rank)
        ],
    }


@pytest.mark.parametrize("legacy", [False, True])
def test_cached_chunks_equal_full_search_and_only_read_needed_conflict_evidence(
    client: TestClient,
    db_session: Session,
    reference: int,
    monkeypatch: pytest.MonkeyPatch,
    legacy: bool,
) -> None:
    if legacy:
        row = db_session.query(PdpjRow).filter_by(review_id=reference).one()
        fields = dict(row.current_fields)
        for key in ("meter_ref", "agenda_ref", "survey_ref"):
            fields.pop(key, None)
        fields["target_ref"] = "NEW"
        row.current_fields = fields
        db_session.get(PdpjReview, reference).revision += 1
        db_session.commit()
    content = "IDPEL,NAMA,NOMOR_METER,ID_TITIK,LAT,LON\n"
    content += (
        "001,Identitas,M900,S900,-6.2,106.8\n"
        "999,Meter lama,M001,S901,-6.2,106.8\n"
        "998,Meter baru,NEW,S902,-6.2,106.8\n"
        "997,Survei,M903,S001,-6.2,106.8\n"
        "002,Master valid,M904,S904,-6.2,106.8\n"
        "996,Tanpa koordinat,M905,S905,,\n"
        "995,Rusak,M906,S906,bad,106.8\n"
        "994,Jauh,M907,S907,-9,110\n"
    ) * 15
    batch = upload(client, "idpel_tidak_ketemu", content)
    full = check(client, "idpel_tidak_ketemu", batch, reference, radius=100)
    process = full["process_id"]
    before = snapshot(db_session, full["latest_run"]["id"], process, 1)
    base = f"/corrections/idpel_tidak_ketemu/checks/{process}"
    response = client.post(
        base + "/retry",
        json={
            "latest_run_id": full["latest_run"]["id"],
            "radius_meters": 100,
            "actor": "Petugas",
            "request_key": "indexed_equivalence",
            "incremental": True,
        },
    )
    assert response.status_code == 200, response.text
    run = response.json()["latest_run"]
    pdpj_index.clear_pdpj_indexes()
    build = Mock(wraps=pdpj_index.build_index)
    monkeypatch.setattr(pdpj_index, "build_index", build)
    reads: list[str] = []

    def capture(
        _conn: Any, _cursor: Any, sql: str, _params: Any, _context: Any, _many: bool
    ) -> None:
        if sql.lstrip().startswith("SELECT") and "pdpj_rows" in sql:
            reads.append(sql)

    while run["status"] != "completed":
        matching = run["processing"]["stage"] == "matching"
        if matching:
            event.listen(db_session.get_bind(), "before_cursor_execute", capture)
        try:
            response = client.post(
                base + "/advance",
                json={
                    "run_id": run["id"],
                    "revision": run["processing"]["revision"],
                    "chunk_size": 100,
                },
            )
        finally:
            if matching:
                event.remove(db_session.get_bind(), "before_cursor_execute", capture)
        assert response.status_code == 200, response.text
        run = response.json()
    assert build.call_count == 1
    scans = [sql for sql in reads if "pdpj_rows.id IN" not in sql]
    assert len(scans) == 1 and "source_records.data" not in scans[0]
    assert snapshot(db_session, run["id"], process, 2) == before
    # A target IDPEL absent from PDPJ must never be added to the exclusion index.
    review = db_session.get(PdpjReview, reference)
    source = db_session.get(UploadBatch, review.batch_id)
    original_index = pdpj_index.get_index(db_session, review, source)
    assert "002" not in original_index.identities
    review.revision += 1
    db_session.commit()
    assert pdpj_index.get_index(db_session, review, source) is not original_index
    assert build.call_count == 2
    assert client.post("/upload/reset").status_code == 200
    assert len(pdpj_index._cache) == 0


def test_partial_publication_keeps_pending_reservations_when_original_review_continues(
    client: TestClient, db_session: Session, partial: dict
) -> None:
    published = publications.approve(client, partial["id"])["published_review"]
    frozen = db_session.get(PdpjReview, published["id"])
    target_id = upload(
        client, "idpel_tidak_ketemu", "IDPEL,LAT,LON\n003,-6.2,106.8\n004,-6.2,106.8\n"
    )
    target = db_session.get(UploadBatch, target_id)
    raw = [
        data
        for (data,) in db_session.query(SourceRecord.data)
        .filter(SourceRecord.batch_id == target_id)
        .order_by(SourceRecord.id)
    ]
    fields = [extract_standard_fields(data, target.column_mapping) for data in raw]
    pdpj_index.clear_pdpj_indexes()
    original = pdpj_index.chunk_context(db_session, frozen, fields, raw, target)
    assert original.identities["003"][0]["pending_validation"] is True
    assert original.identities.get("004", []) == [] and "004" not in original.identities
    source = db_session.get(UploadBatch, frozen.batch_id)
    cached = pdpj_index.get_index(db_session, frozen, source)
    base = f"/pdpj/reviews/{partial['id']}"
    resumed = client.post(base + "/resume").json()
    step(client, resumed)
    client.post(base + "/pause").raise_for_status()
    last = rows(client, partial["id"])[-1]
    changed = client.patch(
        base + f"/rows/{last['id']}",
        json=action(
            client,
            partial["id"],
            fields={"idpel": "004"},
            reason="Identitas dikonfirmasi",
        ),
    )
    assert changed.status_code == 200, changed.text
    second = publications.approve(client, partial["id"])["published_review"]
    assert pdpj_index.get_index(db_session, frozen, source) is cached
    previous = pdpj_index.chunk_context(db_session, frozen, fields, raw, target)
    assert previous.identities["003"] == original.identities["003"]
    current = pdpj_index.chunk_context(
        db_session, db_session.get(PdpjReview, second["id"]), fields, raw, target
    )
    assert "003" not in current.identities and "004" in current.identities
    assert "pending_validation" not in current.identities["004"][0]
